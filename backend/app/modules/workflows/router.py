"""工作流管理 API 路由"""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.data_scope import check_demand_data_permission
from app.core.rbac import require_permissions
from app.core.time import utc_now
from app.core.workspace import ensure_demand_workspace, write_workspace_workflow_metadata
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.demand import Workflow, WorkflowStage, WorkflowTemplate
from app.models.skill import Skill, WorkflowStageSkillBinding
from app.models.user import User
from app.modules.auth.dependencies import get_current_orm_user


router = APIRouter()


class WorkflowResponse(BaseModel):
    id: UUID
    demand_id: UUID
    template_key: str
    workflow_type: str
    current_stage: str
    status: str
    stages: list[dict]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StageAdvanceRequest(BaseModel):
    """推进阶段请求"""
    pass


class StageBlockRequest(BaseModel):
    """阻塞阶段请求"""
    blocked_reason: str


class WorkflowCreateRequest(BaseModel):
    """创建工作流请求"""
    template_key: str = "full"


def create_workflow_stages(db: Session, workflow: Workflow, template: WorkflowTemplate) -> list[WorkflowStage]:
    stages = []
    active_stages = [stage for stage in template.stages if stage.status == "active"]
    if not active_stages:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="工作流模板没有可用阶段")
    for i, template_stage in enumerate(active_stages):
        stage = WorkflowStage(
            workflow_id=workflow.id,
            stage_key=template_stage.stage_key,
            stage_name=template_stage.stage_name,
            sort_order=template_stage.sort_order,
            status="current" if i == 0 else "pending",
            started_at=utc_now() if i == 0 else None,
        )
        db.add(stage)
        stages.append(stage)
    workflow.current_stage = active_stages[0].stage_key
    workflow.template_key = template.key
    workflow.workflow_type = template.workflow_type
    return stages


def _stage_skill_map(db: Session, template_key: str) -> dict[str, list[dict]]:
    bindings = db.scalars(
        select(WorkflowStageSkillBinding)
        .where(WorkflowStageSkillBinding.status == "active")
        .where(WorkflowStageSkillBinding.template_key == template_key)
        .order_by(WorkflowStageSkillBinding.stage_key.asc(), WorkflowStageSkillBinding.order_num.asc())
    ).all()
    if not bindings:
        return {}
    skills = db.scalars(select(Skill).where(Skill.key.in_([binding.skill_key for binding in bindings]))).all()
    skill_by_key = {skill.key: skill for skill in skills}
    result: dict[str, list[dict]] = {}
    for binding in bindings:
        skill = skill_by_key.get(binding.skill_key)
        if not skill or skill.status != "active":
            continue
        result.setdefault(binding.stage_key, []).append(
            {
                "skill_key": binding.skill_key,
                "skill_name": skill.name,
                "skill_role": skill.role,
                "skill_source": skill.source,
                "is_default": binding.is_default,
                "order_num": binding.order_num,
            }
        )
    return result


def serialize_workflow(workflow: Workflow, db: Session | None = None) -> dict:
    stage_skills = _stage_skill_map(db, workflow.template_key) if db else {}
    stages_data = [
        {
            "id": str(stage.id),
            "stage_key": stage.stage_key,
            "stage_name": stage.stage_name,
            "sort_order": stage.sort_order,
            "status": stage.status,
            "started_at": stage.started_at.isoformat() if stage.started_at else None,
            "finished_at": stage.finished_at.isoformat() if stage.finished_at else None,
            "blocked_reason": stage.blocked_reason,
            "skills": stage_skills.get(stage.stage_key, []),
        }
        for stage in workflow.stages
    ]

    return {
        "id": workflow.id,
        "demand_id": workflow.demand_id,
        "template_key": workflow.template_key,
        "workflow_type": workflow.workflow_type,
        "current_stage": workflow.current_stage,
        "status": workflow.status,
        "stages": stages_data,
        "created_at": workflow.created_at,
        "updated_at": workflow.updated_at,
    }


def serialize_template(template: WorkflowTemplate) -> dict:
    return {
        "key": template.key,
        "name": template.name,
        "workflow_type": template.workflow_type,
        "description": template.description,
        "order_num": template.order_num,
        "stages": [
            {
                "stage_key": stage.stage_key,
                "stage_name": stage.stage_name,
                "sort_order": stage.sort_order,
                "description": stage.description,
            }
            for stage in template.stages
            if stage.status == "active"
        ],
    }


@router.get("/workflow-templates", dependencies=[Depends(require_permissions("workflow:view"))])
def list_workflow_templates(
    db: Session = Depends(get_db),
):
    """获取可用工作流模板"""
    templates = db.scalars(
        select(WorkflowTemplate)
        .where(WorkflowTemplate.status == "active")
        .order_by(WorkflowTemplate.order_num.asc(), WorkflowTemplate.key.asc())
    ).all()
    return {"items": [serialize_template(template) for template in templates]}


@router.get("/{demand_id}/workflows", dependencies=[Depends(require_permissions("workflow:view"))])
def list_workflows(
    demand_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    """获取需求下的全部工作流轮次"""
    from app.models.demand import Demand
    demand = db.get(Demand, demand_id)
    if not demand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="需求不存在")

    if not check_demand_data_permission(demand, current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该需求")

    workflows = sorted(demand.workflows, key=lambda item: item.created_at, reverse=True)
    return {"items": [serialize_workflow(workflow, db) for workflow in workflows]}


@router.post("/{demand_id}/workflows", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permissions("workflow:create"))])
def create_workflow(
    demand_id: UUID,
    request: WorkflowCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    """为需求创建新一轮工作流"""
    from app.models.demand import Demand
    demand = db.get(Demand, demand_id)
    if not demand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="需求不存在")

    if not check_demand_data_permission(demand, current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该需求")

    if demand.status == "archived":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="已归档需求不能创建新工作流")

    template = db.scalar(
        select(WorkflowTemplate)
        .where(WorkflowTemplate.key == request.template_key)
        .where(WorkflowTemplate.status == "active")
    )
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工作流模板不存在")

    workflow = Workflow(
        demand_id=demand.id,
        template_key=template.key,
        workflow_type=template.workflow_type,
        current_stage="",
        status="running",
    )
    db.add(workflow)
    db.flush()
    create_workflow_stages(db, workflow, template)
    workspace = ensure_demand_workspace(db, demand, current_user)
    write_workspace_workflow_metadata(db, workspace, workflow)

    audit_log = AuditLog(
        actor_user_id=current_user.id,
        action="workflow.create",
        target_type="workflow",
        target_id=workflow.id,
        metadata_={"demand_id": str(demand.id), "title": demand.title, "template_key": template.key},
    )
    db.add(audit_log)
    db.commit()
    db.refresh(workflow)

    return serialize_workflow(workflow, db)


@router.get("/{demand_id}/workflow", response_model=WorkflowResponse, dependencies=[Depends(require_permissions("workflow:view"))])
def get_workflow(
    demand_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    """获取需求最近一轮工作流，兼容旧入口"""
    from app.models.demand import Demand
    demand = db.get(Demand, demand_id)
    if not demand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="需求不存在")

    if not check_demand_data_permission(demand, current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该需求")

    workflows = sorted(demand.workflows, key=lambda item: item.created_at, reverse=True)
    if not workflows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工作流不存在")

    return serialize_workflow(workflows[0], db)


@router.post("/{workflow_id}/advance", dependencies=[Depends(require_permissions("workflow:advance"))])
def advance_workflow(
    workflow_id: UUID,
    request: StageAdvanceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    """推进工作流阶段到下一阶段。

    规则：
    - 已归档的工作流不能推进。
    - 推进到最后一级阶段后，归档仍需通过 POST /demands/{id}/archive 触发。
    """
    workflow = db.get(Workflow, workflow_id)
    if not workflow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工作流不存在")

    demand = workflow.demand
    if not check_demand_data_permission(demand, current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该需求")

    if workflow.status in {"done", "archived"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="已完成或已归档的工作流不能推进")

    # 查找当前阶段
    current_stage = None
    next_stage = None
    for i, stage in enumerate(workflow.stages):
        if stage.status == "current":
            current_stage = stage
            if i + 1 < len(workflow.stages):
                next_stage = workflow.stages[i + 1]
            break

    if not current_stage:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未找到当前阶段")

    now = utc_now()
    current_stage.status = "passed"
    current_stage.finished_at = now

    if not next_stage:
        workflow.status = "done"
        workflow.updated_at = now
        audit_log = AuditLog(
            actor_user_id=current_user.id,
            action="workflow.complete",
            target_type="workflow",
            target_id=workflow.id,
            metadata_={
                "workflow_id": str(workflow.id),
                "stage": current_stage.stage_key,
            },
        )
        db.add(audit_log)
        db.commit()
        return {"message": f"已完成 {current_stage.stage_name}，工作流已结束"}

    next_stage.status = "current"
    next_stage.started_at = now

    workflow.current_stage = next_stage.stage_key
    workflow.updated_at = now

    audit_log = AuditLog(
        actor_user_id=current_user.id,
        action="workflow.stage.advance",
        target_type="workflow_stage",
        target_id=next_stage.id,
        metadata_={
            "workflow_id": str(workflow.id),
            "from_stage": current_stage.stage_key,
            "to_stage": next_stage.stage_key,
        },
    )
    db.add(audit_log)

    db.commit()

    return {"message": f"已从 {current_stage.stage_name} 推进到 {next_stage.stage_name}"}


@router.post("/{workflow_id}/block", dependencies=[Depends(require_permissions("workflow:block"))])
def block_workflow(
    workflow_id: UUID,
    request: StageBlockRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    """标记当前阶段为阻塞"""
    workflow = db.get(Workflow, workflow_id)
    if not workflow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工作流不存在")

    demand = workflow.demand
    if not check_demand_data_permission(demand, current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该需求")

    if workflow.status == "archived":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="已归档的工作流不能阻塞")

    current_stage = None
    for stage in workflow.stages:
        if stage.status == "current":
            current_stage = stage
            break

    if not current_stage:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未找到当前阶段")

    current_stage.status = "blocked"
    current_stage.blocked_reason = request.blocked_reason

    workflow.status = "blocked"
    workflow.updated_at = utc_now()

    audit_log = AuditLog(
        actor_user_id=current_user.id,
        action="workflow.stage.block",
        target_type="workflow_stage",
        target_id=current_stage.id,
        metadata_={
            "workflow_id": str(workflow.id),
            "stage": current_stage.stage_key,
            "blocked_reason": request.blocked_reason,
        },
    )
    db.add(audit_log)

    db.commit()

    return {"message": f"已标记 {current_stage.stage_name} 为阻塞"}


@router.post("/{workflow_id}/resume", dependencies=[Depends(require_permissions("workflow:block"))])
def resume_workflow(
    workflow_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    """从阻塞状态恢复"""
    workflow = db.get(Workflow, workflow_id)
    if not workflow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工作流不存在")

    demand = workflow.demand
    if not check_demand_data_permission(demand, current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该需求")

    if workflow.status != "blocked":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="工作流未处于阻塞状态")

    blocked_stage = None
    for stage in workflow.stages:
        if stage.status == "blocked":
            blocked_stage = stage
            break

    if not blocked_stage:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未找到阻塞的阶段")

    blocked_stage.status = "current"
    blocked_stage.blocked_reason = None

    workflow.status = "running"
    workflow.updated_at = utc_now()

    audit_log = AuditLog(
        actor_user_id=current_user.id,
        action="workflow.stage.resume",
        target_type="workflow_stage",
        target_id=blocked_stage.id,
        metadata_={
            "workflow_id": str(workflow.id),
            "stage": blocked_stage.stage_key,
        },
    )
    db.add(audit_log)

    db.commit()

    return {"message": f"已恢复 {blocked_stage.stage_name}"}
