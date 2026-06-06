"""组织架构管理 API"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.rbac import require_permissions
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.demand import Demand
from app.models.organization import Company, Department, OrganizationMember
from app.models.user import User
from app.modules.auth.dependencies import get_current_orm_user

router = APIRouter()

ORG_TYPE_LABELS = {
    "department": "部门",
    "project_group": "项目组",
    "dev_group": "开发组",
}

ALLOWED_CHILD_TYPES = {
    None: {"department"},
    "department": {"department", "project_group", "dev_group"},
    "project_group": {"dev_group"},
    "dev_group": set(),
}


class DepartmentPayload(BaseModel):
    company_id: UUID | None = None
    parent_id: UUID | None = None
    org_type: str = Field(default="department", max_length=30)
    name: str = Field(min_length=1, max_length=120)
    order_num: int = Field(default=0)
    status: str = Field(default="active", max_length=20)


class OrganizationMemberPayload(BaseModel):
    user_id: UUID
    member_role: str = Field(default="member", max_length=20)


def _role_names(user: User) -> list[str]:
    return sorted(role.name for role in user.roles)


def is_super_admin(user: User) -> bool:
    return "admin" in _role_names(user)


def resolve_company_id(
    db: Session,
    current_user: User,
    requested_company_id: UUID | None,
    required: bool = False,
) -> UUID | None:
    if is_super_admin(current_user):
        target_company_id = requested_company_id or current_user.company_id
    else:
        if requested_company_id and requested_company_id != current_user.company_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权维护其他公司数据")
        target_company_id = current_user.company_id
    if target_company_id is None:
        if required:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择公司")
        return None
    if db.get(Company, target_company_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="公司不存在")
    return target_company_id


def _compute_ancestors(db: Session, parent_id: UUID | None) -> str:
    """根据父部门计算 ancestors 字符串，格式为逗号分隔且无前导逗号"""
    if parent_id is None:
        return ""
    parent = db.get(Department, parent_id)
    if parent is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="上级组织架构不存在")
    if parent.ancestors:
        return f"{parent.ancestors},{parent.id}"
    return str(parent.id)


def validate_org_type(org_type: str) -> None:
    if org_type not in ORG_TYPE_LABELS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="组织类型不支持")


def validate_parent_child(
    db: Session,
    company_id: UUID,
    parent_id: UUID | None,
    child_type: str,
    current_id: UUID | None = None,
) -> Department | None:
    validate_org_type(child_type)
    parent = None
    parent_type = None
    if parent_id is not None:
        if current_id is not None and parent_id == current_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能将上级设置为自身")
        parent = db.get(Department, parent_id)
        if parent is None or parent.company_id != company_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="上级组织架构不属于当前公司")
        if current_id is not None:
            ancestor_ids = set(filter(None, parent.ancestors.split(",")))
            if str(current_id) in ancestor_ids:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能将上级设置为自身下级")
        parent_type = parent.org_type

    if child_type not in ALLOWED_CHILD_TYPES.get(parent_type, set()):
        parent_label = ORG_TYPE_LABELS.get(parent_type, "根节点") if parent_type else "根节点"
        child_label = ORG_TYPE_LABELS.get(child_type, child_type)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{parent_label}下不能新增或挂载{child_label}",
        )
    return parent


def validate_existing_children(db: Session, dept_id: UUID, org_type: str) -> None:
    children = db.scalars(select(Department).where(Department.parent_id == dept_id)).all()
    allowed_types = ALLOWED_CHILD_TYPES.get(org_type, set())
    invalid_children = [child for child in children if child.org_type not in allowed_types]
    if invalid_children:
        names = "、".join(child.name for child in invalid_children[:5])
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"当前组织类型不允许已有子级：{names}",
        )


def ensure_no_dev_group_bindings(db: Session, dept: Department, next_org_type: str) -> None:
    if dept.org_type != "dev_group" or next_org_type == "dev_group":
        return
    member_count = db.scalar(
        select(func.count()).select_from(OrganizationMember).where(OrganizationMember.department_id == dept.id)
    )
    if member_count and member_count > 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="开发组下存在成员，不能修改为其他类型")

    demand_count = db.scalar(
        select(func.count()).select_from(Demand).where(Demand.department_id == dept.id)
    )
    if demand_count and demand_count > 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="开发组下存在关联需求，不能修改为其他类型")


def serialize_department(dept: Department) -> dict:
    return {
        "id": str(dept.id),
        "company_id": str(dept.company_id),
        "parent_id": str(dept.parent_id) if dept.parent_id else None,
        "ancestors": dept.ancestors,
        "org_type": dept.org_type,
        "name": dept.name,
        "order_num": dept.order_num,
        "status": dept.status,
        "created_at": dept.created_at.isoformat() if dept.created_at else None,
    }


def serialize_member(member: OrganizationMember) -> dict:
    return {
        "id": str(member.id),
        "department_id": str(member.department_id),
        "user_id": str(member.user_id),
        "username": member.user.username,
        "display_name": member.user.display_name,
        "email": member.user.email,
        "member_role": member.member_role,
        "created_at": member.created_at.isoformat() if member.created_at else None,
    }


def _write_audit(
    db: Session,
    current_user: User,
    action: str,
    target_id: UUID,
    metadata: dict,
) -> None:
    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            action=action,
            target_type="department",
            target_id=target_id,
            metadata_=metadata,
        )
    )


@router.get("", dependencies=[Depends(require_permissions("system:department:list"))])
def list_departments(
    company_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    """查询目标公司的所有组织架构。超级管理员可指定公司，普通管理员固定本人公司。"""
    target_company_id = resolve_company_id(db, current_user, company_id)
    query = select(Department)
    if target_company_id is not None:
        query = query.where(Department.company_id == target_company_id)
    query = query.order_by(Department.order_num.asc(), Department.created_at.asc())
    items = db.scalars(query).all()
    return {"items": [serialize_department(d) for d in items], "total": len(items)}


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permissions("system:department:create"))])
def create_department(
    payload: DepartmentPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    """创建组织架构"""
    target_company_id = resolve_company_id(db, current_user, getattr(payload, "company_id", None), required=True)
    validate_parent_child(db, target_company_id, payload.parent_id, payload.org_type)

    ancestors = _compute_ancestors(db, payload.parent_id)
    dept = Department(
        company_id=target_company_id,
        parent_id=payload.parent_id,
        ancestors=ancestors,
        org_type=payload.org_type,
        name=payload.name.strip(),
        order_num=payload.order_num,
        status=payload.status,
    )
    db.add(dept)
    db.flush()
    _write_audit(
        db,
        current_user,
        "system.department.create",
        dept.id,
        {
            "id": str(dept.id),
            "name": dept.name,
            "org_type": dept.org_type,
            "parent_id": str(dept.parent_id) if dept.parent_id else None,
        },
    )
    db.commit()
    db.refresh(dept)
    return serialize_department(dept)


@router.patch("/{dept_id}", dependencies=[Depends(require_permissions("system:department:update"))])
def update_department(
    dept_id: UUID,
    payload: DepartmentPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    """更新组织架构"""
    dept = db.get(Department, dept_id)
    if dept is None or (not is_super_admin(current_user) and dept.company_id != current_user.company_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="组织架构不存在")

    before = {
        "name": dept.name,
        "org_type": dept.org_type,
        "parent_id": str(dept.parent_id) if dept.parent_id else None,
        "order_num": dept.order_num,
        "status": dept.status,
    }

    validate_parent_child(db, dept.company_id, payload.parent_id, payload.org_type, current_id=dept.id)
    validate_existing_children(db, dept.id, payload.org_type)
    ensure_no_dev_group_bindings(db, dept, payload.org_type)

    # 如果修改 parent_id，需要重新计算 ancestors
    if payload.parent_id != dept.parent_id:
        dept.parent_id = payload.parent_id
        dept.ancestors = _compute_ancestors(db, payload.parent_id)

    dept.name = payload.name.strip()
    dept.org_type = payload.org_type
    dept.order_num = payload.order_num
    dept.status = payload.status
    db.flush()
    _write_audit(
        db,
        current_user,
        "system.department.update",
        dept.id,
        {
            "id": str(dept.id),
            "before": before,
            "after": {
                "name": dept.name,
                "org_type": dept.org_type,
                "parent_id": str(dept.parent_id) if dept.parent_id else None,
                "order_num": dept.order_num,
                "status": dept.status,
            },
        },
    )
    db.commit()
    db.refresh(dept)
    return serialize_department(dept)


@router.delete("/{dept_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_permissions("system:department:delete"))])
def delete_department(
    dept_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    """删除部门：存在子部门或绑定用户时禁止删除"""
    dept = db.get(Department, dept_id)
    if dept is None or (not is_super_admin(current_user) and dept.company_id != current_user.company_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="组织架构不存在")

    # 检查子部门
    child_count = db.scalar(
        select(func.count()).select_from(Department).where(Department.parent_id == dept_id)
    )
    if child_count and child_count > 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="组织架构下存在子级，不能删除")

    # 检查绑定用户
    user_count = db.scalar(
        select(func.count()).select_from(User).where(User.department_id == dept_id)
    )
    if user_count and user_count > 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="组织架构下存在绑定用户，不能删除")

    if dept.org_type == "dev_group":
        member_count = db.scalar(
            select(func.count()).select_from(OrganizationMember).where(OrganizationMember.department_id == dept_id)
        )
        if member_count and member_count > 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="开发组下存在成员，不能删除")

        demand_count = db.scalar(
            select(func.count()).select_from(Demand).where(Demand.department_id == dept_id)
        )
        if demand_count and demand_count > 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="开发组下存在关联需求，不能删除")

    _write_audit(
        db,
        current_user,
        "system.department.delete",
        dept.id,
        {"id": str(dept.id), "name": dept.name},
    )
    db.delete(dept)
    db.commit()


@router.get("/{dept_id}/members", dependencies=[Depends(require_permissions("system:department:list"))])
def list_department_members(
    dept_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    dept = db.get(Department, dept_id)
    if dept is None or (not is_super_admin(current_user) and dept.company_id != current_user.company_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="组织架构不存在")
    if dept.org_type != "dev_group":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="成员只能维护在开发组上")

    members = db.scalars(
        select(OrganizationMember)
        .where(OrganizationMember.department_id == dept_id)
        .order_by(OrganizationMember.member_role.asc(), OrganizationMember.created_at.asc())
    ).all()
    return {"items": [serialize_member(member) for member in members], "total": len(members)}


@router.put("/{dept_id}/members", dependencies=[Depends(require_permissions("system:department:update"))])
def save_department_members(
    dept_id: UUID,
    payload: list[OrganizationMemberPayload],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    dept = db.get(Department, dept_id)
    if dept is None or (not is_super_admin(current_user) and dept.company_id != current_user.company_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="组织架构不存在")
    if dept.org_type != "dev_group":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="成员只能维护在开发组上")

    user_ids = [item.user_id for item in payload]
    if len(user_ids) != len(set(user_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="成员不能重复")

    if user_ids:
        users = db.scalars(select(User).where(User.id.in_(user_ids))).all()
        if len(users) != len(user_ids):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="成员用户不存在")
        for user in users:
            if user.company_id != dept.company_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="成员用户不属于当前公司")

    db.query(OrganizationMember).filter(OrganizationMember.department_id == dept_id).delete(synchronize_session=False)
    for item in payload:
        db.add(
            OrganizationMember(
                department_id=dept_id,
                user_id=item.user_id,
                member_role=item.member_role,
            )
        )

    _write_audit(
        db,
        current_user,
        "system.department.members.update",
        dept.id,
        {
            "id": str(dept.id),
            "name": dept.name,
            "members": [{"user_id": str(item.user_id), "member_role": item.member_role} for item in payload],
        },
    )
    db.commit()
    return list_department_members(dept_id, db, current_user)
