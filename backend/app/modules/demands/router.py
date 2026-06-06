"""需求管理 API 路由"""
from datetime import date, datetime
from pathlib import Path
import shutil
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.data_scope import apply_demand_data_scope, check_demand_data_permission
from app.core.rbac import require_permissions
from app.core.time import utc_now
from app.core.workspace import ensure_demand_workspace
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.agent_run import AgentRun
from app.models.artifact import WorkflowArtifact
from app.models.code_context import CodeContextScanResult, CodeContextSnapshot
from app.models.demand import Demand, DemandMember, DemandWorkspace
from app.models.local_bridge import DemandLocalProject, LocalBridgeCommand
from app.models.organization import Department, OrganizationMember
from app.models.review import Review
from app.models.skill import SkillRun, StageGateCheck, StageSession
from app.models.user import User
from app.modules.auth.dependencies import get_current_orm_user


router = APIRouter()


def remove_workspace_directory(root_path: str | None) -> bool:
    if not root_path:
        return False
    target = Path(root_path).expanduser().resolve()
    if not target.exists() or not target.is_dir():
        return False
    if "demands" not in target.parts:
        return False
    shutil.rmtree(target)
    return True


# Pydantic Schemas
class DemandCreate(BaseModel):
    title: str
    type: str  # new_business, new_project, optimization, bugfix, refactor
    description: str
    expected_live_at: str | None = None
    repository_id: UUID | None = None
    department_id: UUID | None = None


class DemandUpdate(BaseModel):
    title: str | None = None
    type: str | None = None
    description: str | None = None
    expected_live_at: str | None = None
    repository_id: UUID | None = None
    department_id: UUID | None = None
    status: str | None = None


class DemandMemberPayload(BaseModel):
    user_id: UUID
    member_role: str


class ImportOrgMembersPayload(BaseModel):
    department_id: UUID | None = None


class DemandResponse(BaseModel):
    id: UUID
    title: str
    type: str
    description: str
    expected_live_at: str | None
    repository_id: UUID | None
    status: str
    company_id: UUID
    department_id: UUID
    created_by: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


def serialize_demand_member(member: DemandMember) -> dict:
    return {
        "id": str(member.id),
        "demand_id": str(member.demand_id),
        "user_id": str(member.user_id),
        "username": member.user.username,
        "display_name": member.user.display_name,
        "email": member.user.email,
        "member_role": member.member_role,
        "created_at": member.created_at.isoformat() if member.created_at else None,
    }


def serialize_org_member_as_user_option(member: OrganizationMember) -> dict:
    return {
        "id": str(member.id),
        "user_id": str(member.user_id),
        "username": member.user.username,
        "display_name": member.user.display_name,
        "email": member.user.email,
        "member_role": member.member_role,
        "created_at": member.created_at.isoformat() if member.created_at else None,
    }


def serialize_demand(demand: Demand) -> dict:
    return {
        "id": str(demand.id),
        "title": demand.title,
        "type": demand.type,
        "description": demand.description,
        "expected_live_at": demand.expected_live_at.isoformat() if demand.expected_live_at else None,
        "repository_id": str(demand.repository_id) if demand.repository_id else None,
        "status": demand.status,
        "company_id": str(demand.company_id),
        "department_id": str(demand.department_id),
        "department_name": demand.department.name if demand.department else None,
        "created_by": str(demand.created_by),
        "creator_name": demand.creator.display_name if demand.creator else None,
        "members": [serialize_demand_member(member) for member in demand.members],
        "created_at": demand.created_at.isoformat() if demand.created_at else None,
        "updated_at": demand.updated_at.isoformat() if demand.updated_at else None,
    }


def parse_expected_live_at(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def resolve_demand_department(
    db: Session,
    current_user: User,
    department_id: UUID | None,
) -> Department:
    target_department_id = department_id or current_user.department_id
    if not current_user.company_id or not target_department_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请选择需求归属开发组"
        )
    department = db.get(Department, target_department_id)
    if department is None or department.company_id != current_user.company_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="需求归属开发组不存在")
    if department.status != "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="需求归属开发组已停用")
    if department.org_type != "dev_group":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="需求只能归属到开发组")
    return department


def import_organization_members_to_demand(
    db: Session,
    demand: Demand,
    department_id: UUID,
    fail_when_empty: bool = True,
) -> tuple[Department, int]:
    department = db.get(Department, department_id)
    if department is None or department.company_id != demand.company_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="开发组不存在")
    if department.org_type != "dev_group":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="只能导入开发组成员")

    org_members = db.scalars(
        select(OrganizationMember)
        .where(OrganizationMember.department_id == department_id)
        .order_by(OrganizationMember.member_role.asc(), OrganizationMember.created_at.asc())
    ).all()
    if not org_members:
        if fail_when_empty:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前组织架构暂无成员")
        return department, 0

    existing_user_ids = {
        item.user_id
        for item in db.scalars(select(DemandMember).where(DemandMember.demand_id == demand.id)).all()
    }
    imported = 0
    for member in org_members:
        if member.user_id in existing_user_ids:
            continue
        db.add(
            DemandMember(
                demand_id=demand.id,
                user_id=member.user_id,
                member_role="owner" if member.member_role == "leader" else "viewer",
            )
        )
        imported += 1
    return department, imported


@router.get("/", dependencies=[Depends(require_permissions("demand:list"))])
def list_demands(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
    title: str | None = None,
    type: str | None = None,
    status: str | None = None,
):
    """查询需求列表（应用数据权限）"""
    query = select(Demand)

    # 应用数据权限过滤（已强制公司边界）
    query = apply_demand_data_scope(query, current_user, db)

    if title:
        query = query.where(Demand.title.contains(title))
    if type:
        query = query.where(Demand.type == type)
    if status:
        query = query.where(Demand.status == status)

    query = query.order_by(Demand.created_at.desc())

    demands = db.execute(query).scalars().all()
    return [serialize_demand(demand) for demand in demands]


@router.post("/", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permissions("demand:create"))])
def create_demand(
    demand_in: DemandCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    """创建需求（自动创建 workflow 和 stages，写入审计日志）"""
    if not current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="系统级账号不能直接创建需求，请使用有公司归属的账号"
        )
    department = resolve_demand_department(db, current_user, demand_in.department_id)

    demand = Demand(
        title=demand_in.title,
        type=demand_in.type,
        description=demand_in.description,
        expected_live_at=parse_expected_live_at(demand_in.expected_live_at),
        repository_id=demand_in.repository_id,
        status="active",
        company_id=current_user.company_id,
        department_id=department.id,
        created_by=current_user.id,
    )
    db.add(demand)
    db.flush()
    db.add(
        DemandMember(
            demand_id=demand.id,
            user_id=current_user.id,
            member_role="owner",
        )
    )
    db.flush()
    import_department, imported_members = import_organization_members_to_demand(
        db,
        demand,
        department.id,
        fail_when_empty=False,
    )
    workspace = ensure_demand_workspace(db, demand, current_user)

    audit_log = AuditLog(
        actor_user_id=current_user.id,
        action="demand.create",
        target_type="demand",
        target_id=demand.id,
        metadata_={
            "title": demand.title,
            "type": demand.type,
            "department_id": str(import_department.id),
            "department_name": import_department.name,
            "imported_members": imported_members,
            "workspace_root": workspace.root_path,
        },
    )
    db.add(audit_log)

    db.commit()
    db.refresh(demand)

    return serialize_demand(demand)


@router.get("/{demand_id}", dependencies=[Depends(require_permissions("demand:list"))])
def get_demand(
    demand_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    """获取需求详情（应用数据权限）"""
    demand = db.get(Demand, demand_id)
    if not demand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="需求不存在")

    if not check_demand_data_permission(demand, current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该需求")

    return serialize_demand(demand)


@router.patch("/{demand_id}", dependencies=[Depends(require_permissions("demand:update"))])
def update_demand(
    demand_id: UUID,
    demand_in: DemandUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    """更新需求"""
    demand = db.get(Demand, demand_id)
    if not demand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="需求不存在")

    if not check_demand_data_permission(demand, current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该需求")

    update_data = demand_in.model_dump(exclude_unset=True)
    if "expected_live_at" in update_data:
        update_data["expected_live_at"] = parse_expected_live_at(update_data["expected_live_at"])
    if "department_id" in update_data:
        update_data["department_id"] = resolve_demand_department(db, current_user, update_data["department_id"]).id
    for field, value in update_data.items():
        setattr(demand, field, value)

    demand.updated_at = utc_now()

    audit_log = AuditLog(
        actor_user_id=current_user.id,
        action="demand.update",
        target_type="demand",
        target_id=demand.id,
        metadata_=update_data,
    )
    db.add(audit_log)

    db.commit()
    db.refresh(demand)

    return serialize_demand(demand)


@router.delete("/{demand_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_permissions("demand:delete"))])
def delete_demand(
    demand_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    """删除需求及其工作流、成员、产物、AI 会话、Bridge 绑定和工作空间文件。"""
    demand = db.get(Demand, demand_id)
    if not demand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="需求不存在")

    if not check_demand_data_permission(demand, current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该需求")

    workspace = db.scalar(select(DemandWorkspace).where(DemandWorkspace.demand_id == demand.id))
    workspace_root_path = workspace.root_path if workspace else None
    audit_log = AuditLog(
        actor_user_id=current_user.id,
        action="demand.delete",
        target_type="demand",
        target_id=demand.id,
        metadata_={"title": demand.title, "workspace_root": workspace_root_path},
    )
    db.add(audit_log)

    # 显式清理需求子数据，避免部分 SET NULL 外键在需求删除后留下业务残留。
    db.execute(delete(LocalBridgeCommand).where(LocalBridgeCommand.demand_id == demand.id))
    db.execute(delete(DemandLocalProject).where(DemandLocalProject.demand_id == demand.id))
    db.execute(delete(CodeContextScanResult).where(CodeContextScanResult.demand_id == demand.id))
    db.execute(delete(CodeContextSnapshot).where(CodeContextSnapshot.demand_id == demand.id))
    db.execute(delete(StageGateCheck).where(StageGateCheck.demand_id == demand.id))
    db.execute(delete(SkillRun).where(SkillRun.demand_id == demand.id))
    db.execute(delete(StageSession).where(StageSession.demand_id == demand.id))
    db.execute(delete(WorkflowArtifact).where(WorkflowArtifact.demand_id == demand.id))
    db.execute(delete(AgentRun).where(AgentRun.demand_id == demand.id))
    db.execute(delete(Review).where(Review.demand_id == demand.id))
    db.execute(delete(DemandMember).where(DemandMember.demand_id == demand.id))
    db.execute(delete(DemandWorkspace).where(DemandWorkspace.demand_id == demand.id))
    db.flush()

    db.delete(demand)
    db.commit()
    remove_workspace_directory(workspace_root_path)


@router.post("/{demand_id}/archive", dependencies=[Depends(require_permissions("demand:archive"))])
def archive_demand(
    demand_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    """
    归档需求：

    - demand.status = archived
    - workflow.status = archived
    - 当前阶段设为 passed
    - delivery_archive 阶段设为 passed
    - workflow.current_stage = delivery_archive
    """
    demand = db.get(Demand, demand_id)
    if not demand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="需求不存在")

    if not check_demand_data_permission(demand, current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该需求")

    now = utc_now()
    demand.status = "archived"
    demand.updated_at = now

    for workflow in demand.workflows:
        workflow.status = "archived"
        workflow.updated_at = now

        # 处理阶段：当前阶段和交付归档阶段都设为 passed
        for stage in workflow.stages:
            if stage.stage_key == workflow.current_stage:
                stage.status = "passed"
                stage.finished_at = now
            if stage.stage_key == "delivery_archive":
                stage.status = "passed"
                stage.finished_at = now

        workflow.current_stage = "delivery_archive"

    audit_log = AuditLog(
        actor_user_id=current_user.id,
        action="demand.archive",
        target_type="demand",
        target_id=demand.id,
        metadata_={"title": demand.title},
    )
    db.add(audit_log)

    db.commit()
    db.refresh(demand)

    return serialize_demand(demand)


@router.get("/{demand_id}/members", dependencies=[Depends(require_permissions("demand:list"))])
def list_demand_members(
    demand_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    demand = db.get(Demand, demand_id)
    if not demand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="需求不存在")
    if not check_demand_data_permission(demand, current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该需求")

    members = db.scalars(
        select(DemandMember)
        .where(DemandMember.demand_id == demand_id)
        .order_by(DemandMember.member_role.asc(), DemandMember.created_at.asc())
    ).all()
    return {"items": [serialize_demand_member(member) for member in members], "total": len(members)}


@router.get("/{demand_id}/department-members", dependencies=[Depends(require_permissions("demand:update"))])
def list_demand_department_members(
    demand_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    demand = db.get(Demand, demand_id)
    if not demand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="需求不存在")
    if not check_demand_data_permission(demand, current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该需求")

    department = db.get(Department, demand.department_id)
    if department is None or department.org_type != "dev_group":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="需求归属开发组不存在")

    members = db.scalars(
        select(OrganizationMember)
        .where(OrganizationMember.department_id == demand.department_id)
        .order_by(OrganizationMember.member_role.asc(), OrganizationMember.created_at.asc())
    ).all()
    return {"items": [serialize_org_member_as_user_option(member) for member in members], "total": len(members)}


@router.put("/{demand_id}/members", dependencies=[Depends(require_permissions("demand:update"))])
def save_demand_members(
    demand_id: UUID,
    payload: list[DemandMemberPayload],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    demand = db.get(Demand, demand_id)
    if not demand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="需求不存在")
    if not check_demand_data_permission(demand, current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该需求")

    user_ids = [item.user_id for item in payload]
    if len(user_ids) != len(set(user_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="需求成员不能重复")

    if user_ids:
        users = db.scalars(select(User).where(User.id.in_(user_ids))).all()
        if len(users) != len(user_ids):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="成员用户不存在")
        for user in users:
            if user.company_id != demand.company_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="成员用户不属于需求所在公司")

    db.query(DemandMember).filter(DemandMember.demand_id == demand_id).delete(synchronize_session=False)
    for item in payload:
        db.add(DemandMember(demand_id=demand_id, user_id=item.user_id, member_role=item.member_role))

    audit_log = AuditLog(
        actor_user_id=current_user.id,
        action="demand.members.update",
        target_type="demand",
        target_id=demand.id,
        metadata_={"members": [{"user_id": str(item.user_id), "member_role": item.member_role} for item in payload]},
    )
    db.add(audit_log)
    db.commit()
    return list_demand_members(demand_id, db, current_user)


@router.post("/{demand_id}/members/import-org", dependencies=[Depends(require_permissions("demand:update"))])
def import_org_members(
    demand_id: UUID,
    payload: ImportOrgMembersPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    demand = db.get(Demand, demand_id)
    if not demand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="需求不存在")
    if not check_demand_data_permission(demand, current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该需求")

    department_id = payload.department_id or demand.department_id
    department, imported = import_organization_members_to_demand(db, demand, department_id)

    audit_log = AuditLog(
        actor_user_id=current_user.id,
        action="demand.members.import_org",
        target_type="demand",
        target_id=demand.id,
        metadata_={
            "department_id": str(department_id),
            "department_name": department.name,
            "imported": imported,
        },
    )
    db.add(audit_log)
    db.commit()
    return list_demand_members(demand_id, db, current_user)
