"""需求工作台执行记录与阶段产物 API。"""
from datetime import datetime
import json
import logging
from types import SimpleNamespace
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.ai_runtime import snapshot_model_provider, stream_chat_completion
from app.core.data_scope import check_demand_data_permission
from app.core.rbac import require_permissions
from app.core.time import utc_now
from app.core.workspace import ensure_demand_workspace, read_workspace_file, stage_file_path, write_workspace_file
from app.db.session import SessionLocal, get_db
from app.models.artifact import WorkflowArtifact
from app.models.audit import AuditLog
from app.models.ai_model import ModelProvider
from app.models.code_context import CodeContextSnapshot
from app.models.demand import Demand, Workflow, WorkflowStage
from app.models.skill import Skill, SkillRun, StageCommand, StageGateCheck, StageMessage, StageSession, StageToolCall
from app.models.user import User
from app.modules.auth.dependencies import get_current_orm_user
from app.modules.skills.router import _read_remote_file


router = APIRouter()
logger = logging.getLogger(__name__)


class SkillRunCreate(BaseModel):
    workflow_id: UUID
    workflow_stage_id: UUID | None = None
    stage: str
    skill_key: str
    status: str = "success"
    input_summary: str | None = None
    output_summary: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class ArtifactCreate(BaseModel):
    workflow_id: UUID
    workflow_stage_id: UUID | None = None
    stage: str
    artifact_type: str
    title: str
    content: str = ""


class ArtifactUpdate(BaseModel):
    artifact_type: str | None = None
    title: str | None = None
    content: str | None = None


class StageMessageCreate(BaseModel):
    content: str


class StageSessionComplete(BaseModel):
    artifact_title: str | None = None
    artifact_type: str | None = None
    artifact_content: str | None = None


def _get_demand_with_permission(demand_id: UUID, current_user: User, db: Session) -> Demand:
    demand = db.get(Demand, demand_id)
    if not demand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="需求不存在")
    if not check_demand_data_permission(demand, current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该需求")
    return demand


def _get_workflow_for_demand(demand_id: UUID, workflow_id: UUID, db: Session) -> Workflow:
    workflow = db.get(Workflow, workflow_id)
    if not workflow or workflow.demand_id != demand_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工作流不存在")
    return workflow


def _get_stage_for_workflow(
    workflow: Workflow,
    stage_key: str,
    workflow_stage_id: UUID | None,
) -> WorkflowStage:
    stage = None
    if workflow_stage_id:
        stage = next((item for item in workflow.stages if item.id == workflow_stage_id), None)
    if not stage:
        stage = next((item for item in workflow.stages if item.stage_key == stage_key), None)
    if not stage:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工作流阶段不存在")
    if stage.stage_key != stage_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="阶段标识不一致")
    return stage


def _serialize_skill_run(item: SkillRun) -> dict:
    return {
        "id": str(item.id),
        "demand_id": str(item.demand_id),
        "workflow_id": str(item.workflow_id),
        "workflow_stage_id": str(item.workflow_stage_id) if item.workflow_stage_id else None,
        "stage": item.stage,
        "skill_key": item.skill_key,
        "skill_name": item.skill_name,
        "skill_role": item.skill_role,
        "skill_source": item.skill_source,
        "status": item.status,
        "input_summary": item.input_summary,
        "output_summary": item.output_summary,
        "started_at": item.started_at.isoformat() if item.started_at else None,
        "finished_at": item.finished_at.isoformat() if item.finished_at else None,
        "created_by": str(item.created_by),
        "creator_name": item.creator.display_name or item.creator.username if item.creator else None,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _serialize_artifact(item: WorkflowArtifact) -> dict:
    return {
        "id": str(item.id),
        "demand_id": str(item.demand_id),
        "workflow_id": str(item.workflow_id),
        "workflow_stage_id": str(item.workflow_stage_id) if item.workflow_stage_id else None,
        "stage": item.stage,
        "artifact_type": item.artifact_type,
        "title": item.title,
        "content": item.content,
        "version": item.version,
        "version_no": item.version_no,
        "is_current": item.is_current,
        "source_session_id": str(item.source_session_id) if item.source_session_id else None,
        "created_by": str(item.created_by),
        "creator_name": item.creator.display_name or item.creator.username if item.creator else None,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _artifact_type_by_stage(stage_key: str) -> str:
    return {
        "demand_planning": "prd",
        "product_design": "openspec_design",
        "development": "dev_plan",
        "acceptance_review": "test_plan",
        "issue_confirm": "acceptance_criteria",
        "fix_implementation": "dev_plan",
        "regression_verify": "test_plan",
        "change_confirm": "acceptance_criteria",
        "self_test": "dev_plan",
        "delivery_archive": "delivery_summary",
    }.get(stage_key, "other")


def _serialize_message(item: StageMessage) -> dict:
    return {
        "id": str(item.id),
        "session_id": str(item.session_id),
        "role": item.role,
        "content": item.content,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def _serialize_stage_session(item: StageSession, messages: list[StageMessage] | None = None) -> dict:
    return {
        "id": str(item.id),
        "demand_id": str(item.demand_id),
        "workflow_id": str(item.workflow_id),
        "workflow_stage_id": str(item.workflow_stage_id),
        "stage": item.stage,
        "skill_key": item.skill_key,
        "skill_name": item.skill_name,
        "status": item.status,
        "draft_title": item.draft_title,
        "draft_type": item.draft_type,
        "draft_content": item.draft_content,
        "created_by": str(item.created_by),
        "completed_at": item.completed_at.isoformat() if item.completed_at else None,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        "messages": [_serialize_message(message) for message in messages] if messages is not None else None,
    }


def _serialize_gate_check(item: StageGateCheck) -> dict:
    return {
        "id": str(item.id),
        "session_id": str(item.session_id),
        "demand_id": str(item.demand_id),
        "workflow_id": str(item.workflow_id),
        "workflow_stage_id": str(item.workflow_stage_id),
        "stage": item.stage,
        "status": item.status,
        "summary": item.summary,
        "details": item.details,
        "checked_by": str(item.checked_by),
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _serialize_stage_command(item: StageCommand) -> dict:
    return {
        "id": str(item.id),
        "session_id": str(item.session_id),
        "command": item.command,
        "prompt": item.prompt,
        "status": item.status,
        "result_summary": item.result_summary,
        "created_by": str(item.created_by),
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _serialize_tool_call(item: StageToolCall) -> dict:
    return {
        "id": str(item.id),
        "session_id": str(item.session_id),
        "tool_name": item.tool_name,
        "input_summary": item.input_summary,
        "output_summary": item.output_summary,
        "status": item.status,
        "created_by": str(item.created_by),
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _extract_command(content: str) -> str | None:
    first_token = content.strip().split(maxsplit=1)[0] if content.strip() else ""
    if first_token.startswith("/") and len(first_token) > 1:
        return first_token[:80]
    return None


def _extract_markdown_section(content: str, heading: str) -> str:
    lines = content.splitlines()
    capture = False
    section: list[str] = []
    target = heading.strip().lower()
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            title = stripped.removeprefix("## ").strip().lower()
            if capture:
                break
            capture = title == target
            continue
        if capture:
            section.append(line)
    return "\n".join(section).strip()


def _extract_bullet_items(section: str) -> list[str]:
    items: list[str] = []
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith(("- ", "* ")):
            item = stripped[2:].strip()
            if item:
                items.append(item)
    return items


def _keyword_present(content: str, text: str) -> bool:
    normalized = content.lower()
    raw = text.strip()
    if not raw:
        return True
    candidates = [raw]
    for separator in ["、", "/", "／", "或", "和", "与", "：", ":"]:
        if separator in raw:
            candidates.extend(part.strip() for part in raw.split(separator) if part.strip())
    keywords = []
    for candidate in candidates:
        cleaned = candidate.strip(" `。；;，,（）()[]【】")
        if 2 <= len(cleaned) <= 18:
            keywords.append(cleaned)
    return any(keyword.lower() in normalized for keyword in keywords)


def _skill_semantic_missing_items(skill_instruction: str, content: str) -> list[str]:
    # 从 Skill.md 的 Output/Gate 中抽取轻量语义要求，作为结构化 Gate 之外的补充校验。
    missing: list[str] = []
    output_items = _extract_bullet_items(_extract_markdown_section(skill_instruction, "Output"))
    for item in output_items:
        if not _keyword_present(content, item):
            missing.append(f"Skill Output 缺少：{item}")

    gate_text = _extract_markdown_section(skill_instruction, "Gate")
    for keyword in ["验收", "验证", "测试", "结论", "风险", "阻塞", "摘要", "范围", "用户故事", "待确认"]:
        if keyword in gate_text and keyword not in content:
            missing.append(f"Skill Gate 要求包含：{keyword}")
    if any(word in gate_text for word in ["不得进入", "不得标记", "未确认", "没有"]) and "待确认" in content and "无" not in content:
        missing.append("Skill Gate 存在不得推进条件，产物仍包含待确认内容")
    return list(dict.fromkeys(missing))


def _extract_artifact_content(reply: str) -> str | None:
    """从 AI 回复中提取明确声明要写入工作区文件的产物内容。

    普通聊天回复、澄清问题和过程分析只保存到会话消息，不应自动覆盖阶段文档。
    只有模型按约定输出 <artifact>...</artifact> 或 fenced artifact 代码块时才更新文档。
    """
    normalized = reply.strip()
    if not normalized:
        return None

    tag_start = normalized.find("<artifact>")
    tag_end = normalized.find("</artifact>")
    if tag_start >= 0 and tag_end > tag_start:
        artifact = normalized[tag_start + len("<artifact>"):tag_end].strip()
        return artifact or None

    fence_markers = ["```artifact", "```markdown artifact", "```md artifact"]
    for marker in fence_markers:
        start = normalized.lower().find(marker)
        if start < 0:
            continue
        content_start = normalized.find("\n", start)
        if content_start < 0:
            continue
        end = normalized.find("```", content_start + 1)
        if end < 0:
            continue
        artifact = normalized[content_start + 1:end].strip()
        return artifact or None

    return None


def _run_gate_check(
    db: Session,
    session: StageSession,
    stage: WorkflowStage,
    content: str,
    current_user: User,
    skill_instruction: str = "",
) -> StageGateCheck:
    # Gate 先做平台通用的产物完整性检查，再叠加当前阶段 Skill 的语义化要求。
    normalized = content.strip()
    missing: list[str] = []
    if len(normalized) < 80:
        missing.append("阶段产物内容过少")
    if not normalized.startswith("#"):
        missing.append("阶段产物需要使用 Markdown 标题组织内容")
    if "TODO" in normalized.upper() or "待补充" in normalized:
        missing.append("阶段产物仍包含明显待补充内容")
    if stage.stage_key in {"demand_planning", "issue_confirm", "change_confirm"} and "验收" not in normalized:
        missing.append("需求确认类阶段需要包含验收口径")
    if stage.stage_key in {"development", "fix_implementation", "self_test"} and not any(keyword in normalized for keyword in ["验证", "自测", "测试"]):
        missing.append("实施类阶段需要包含验证或自测记录")
    if stage.stage_key in {"acceptance_review", "regression_verify"} and not any(keyword in normalized for keyword in ["用例", "结论", "通过", "失败"]):
        missing.append("测试验收类阶段需要包含测试用例或验收结论")
    if skill_instruction:
        missing.extend(_skill_semantic_missing_items(skill_instruction, normalized))

    gate = StageGateCheck(
        session_id=session.id,
        demand_id=session.demand_id,
        workflow_id=session.workflow_id,
        workflow_stage_id=session.workflow_stage_id,
        stage=session.stage,
        status="passed" if not missing else "failed",
        summary="Gate 校验通过" if not missing else "Gate 校验未通过",
        details="\n".join(f"- {item}" for item in missing) if missing else "基础产物完整性检查通过。",
        checked_by=current_user.id,
    )
    db.add(gate)
    return gate


def _create_artifact_version(
    db: Session,
    session: StageSession | None,
    demand_id: UUID,
    workflow_id: UUID,
    stage: WorkflowStage,
    artifact_type: str,
    title: str,
    content: str,
    current_user: User,
) -> WorkflowArtifact:
    existing_versions = db.scalars(
        select(WorkflowArtifact)
        .where(WorkflowArtifact.workflow_id == workflow_id)
        .where(WorkflowArtifact.workflow_stage_id == stage.id)
        .where(WorkflowArtifact.artifact_type == artifact_type)
    ).all()
    for item in existing_versions:
        item.is_current = False
    next_version = max([item.version_no for item in existing_versions] or [0]) + 1
    artifact = WorkflowArtifact(
        demand_id=demand_id,
        workflow_id=workflow_id,
        workflow_stage_id=stage.id,
        stage=stage.stage_key,
        artifact_type=artifact_type,
        title=title,
        content=content,
        version=next_version,
        version_no=next_version,
        is_current=True,
        source_session_id=session.id if session else None,
        created_by=current_user.id,
    )
    db.add(artifact)
    return artifact


def _stage_default_skill(db: Session, workflow: Workflow, stage: WorkflowStage) -> Skill:
    from app.models.skill import WorkflowStageSkillBinding

    binding = db.scalar(
        select(WorkflowStageSkillBinding)
        .where(WorkflowStageSkillBinding.template_key == workflow.template_key)
        .where(WorkflowStageSkillBinding.stage_key == stage.stage_key)
        .where(WorkflowStageSkillBinding.status == "active")
        .order_by(WorkflowStageSkillBinding.is_default.desc(), WorkflowStageSkillBinding.order_num.asc())
    )
    if not binding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="当前阶段未绑定 Skill")
    skill = db.scalar(select(Skill).where(Skill.key == binding.skill_key))
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="当前阶段默认 Skill 不存在")
    return skill


def _default_model_provider(db: Session, current_user: User) -> ModelProvider:
    provider = db.scalar(
        select(ModelProvider)
        .where(ModelProvider.user_id == current_user.id)
        .where(ModelProvider.status == "active")
        .order_by(ModelProvider.is_default.desc(), ModelProvider.created_at.asc())
    )
    if not provider:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先在模型配置中添加可用模型")
    return provider


async def _load_skill_instruction(skill: Skill) -> str:
    entry_file = skill.entry_file or "SKILL.md"
    try:
        content = await _read_remote_file(skill, entry_file)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Read remote skill failed: skill_key=%s", skill.key)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Skill 内容读取失败：{exc.__class__.__name__}",
        ) from exc
    if not content.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"当前阶段 Skill「{skill.name}」未读取到 {entry_file} 内容，请先检查 Skill 仓库来源配置",
        )
    return content[:20000]


async def _build_stage_prompts(
    db: Session,
    demand: Demand,
    workflow: Workflow,
    stage: WorkflowStage,
    skill: Skill,
    workspace,
    user_content: str,
) -> tuple[str, str]:
    skill_instruction = await _load_skill_instruction(skill)
    file_paths = [
        ".opendevflow/context.md",
        ".opendevflow/stages.yml",
        ".opendevflow/skills.yml",
        stage_file_path(stage.stage_key),
    ]
    files = []
    seen = set()
    for file_path in file_paths:
        if file_path in seen:
            continue
        seen.add(file_path)
        content = read_workspace_file(workspace, file_path)
        if content:
            files.append(f"## {file_path}\n```text\n{content[:6000]}\n```")
    # 需求澄清、PRD、测试计划等非编码阶段也读取最新代码快照，避免 AI 脱离现有业务事实。
    code_context = db.scalar(
        select(CodeContextSnapshot)
        .where(CodeContextSnapshot.demand_id == demand.id)
        .where(CodeContextSnapshot.is_current.is_(True))
        .order_by(CodeContextSnapshot.created_at.desc())
    )
    code_context_text = (
        f"## 当前代码上下文快照\n"
        f"- 来源：{code_context.source_type}\n"
        f"- 项目数：{code_context.project_count}\n"
        f"- 根目录：{code_context.root_path or '-'}\n\n"
        f"```markdown\n{code_context.snapshot_content[:12000]}\n```"
        if code_context
        else "暂无代码上下文快照。若需要基于现有业务事实分析，请先通过本地 Bridge 生成快照。"
    )
    system_prompt = (
        "你是 OpenDevFlow 平台中的阶段 AI 助手，需要基于当前需求、工作流阶段、Skill 和工作空间文件推进交付。\n"
        "回答使用中文，直接给出可执行建议，不要编造不存在的信息。\n"
        "普通澄清、提问、分析和建议只作为聊天回复输出，不要包裹为产物。\n"
        "只有当用户明确要求生成/更新当前阶段文档，或你判断信息已经足够并需要写入工作区文件时，才在回复中附加一个独立产物块。\n"
        "产物块必须使用 <artifact> 和 </artifact> 包裹，标签内部放完整 Markdown 文档；标签外可以保留简短说明。\n"
        "如果信息不足，先提出明确问题，不要输出 <artifact>。\n\n"
        "# 当前阶段必须遵循的 Skill 指令\n"
        f"- Skill：{skill.name} ({skill.key})\n"
        f"- 来源：{skill.git_url or '-'} @ {skill.git_ref or 'main'} / {skill.sub_path or ''}/{skill.entry_file or 'SKILL.md'}\n\n"
        "```markdown\n"
        f"{skill_instruction}\n"
        "```"
    )
    user_prompt = (
        f"# 需求\n"
        f"- 标题：{demand.title}\n"
        f"- 类型：{demand.type}\n"
        f"- 状态：{demand.status}\n\n"
        f"# 工作流\n"
        f"- 模板：{workflow.template_key}\n"
        f"- 当前阶段：{stage.stage_name} ({stage.stage_key})\n"
        f"- Skill：{skill.name} ({skill.key})\n"
        f"- Skill 描述：{skill.description}\n\n"
        f"# 工作空间文件\n"
        f"{chr(10).join(files) if files else '暂无工作空间文件内容。'}\n\n"
        f"# 代码上下文\n"
        f"{code_context_text}\n\n"
        f"# 用户消息\n{user_content}"
    )
    return system_prompt, user_prompt


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _mock_ai_reply(demand: Demand, workflow: Workflow, stage: WorkflowStage, skill: Skill, user_content: str) -> tuple[str, str]:
    reply = (
        f"我会按「{stage.stage_name}」阶段推进，当前使用 Skill「{skill.name}」。\n\n"
        f"已记录你的输入：{user_content}\n\n"
        "下一步请继续补充目标、边界、验收口径或限制条件；如果信息已经足够，可以直接确认阶段产物。"
    )
    draft = (
        f"# {stage.stage_name}产物草稿\n\n"
        f"## 需求\n{demand.title}\n\n"
        f"## 阶段目标\n{stage.stage_name}\n\n"
        f"## 已确认信息\n- {user_content}\n\n"
        f"## 待确认\n- 是否还有补充背景、边界或验收要求。\n"
    )
    return reply, draft


@router.get("/{demand_id}/skill-runs", dependencies=[Depends(require_permissions("skill_run:view"))])
def list_skill_runs(
    demand_id: UUID,
    workflow_id: UUID | None = None,
    stage: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    _get_demand_with_permission(demand_id, current_user, db)
    query = select(SkillRun).where(SkillRun.demand_id == demand_id)
    if workflow_id:
        query = query.where(SkillRun.workflow_id == workflow_id)
    if stage:
        query = query.where(SkillRun.stage == stage)
    query = query.order_by(SkillRun.created_at.desc())
    return {"items": [_serialize_skill_run(item) for item in db.scalars(query).all()]}


@router.post("/{demand_id}/skill-runs", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permissions("skill_run:create"))])
def create_skill_run(
    demand_id: UUID,
    payload: SkillRunCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    _get_demand_with_permission(demand_id, current_user, db)
    workflow = _get_workflow_for_demand(demand_id, payload.workflow_id, db)
    stage = _get_stage_for_workflow(workflow, payload.stage, payload.workflow_stage_id)
    skill = db.scalar(select(Skill).where(Skill.key == payload.skill_key))
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill 不存在")

    now = utc_now()
    skill_run = SkillRun(
        demand_id=demand_id,
        workflow_id=workflow.id,
        workflow_stage_id=stage.id,
        stage=stage.stage_key,
        skill_key=skill.key,
        skill_name=skill.name,
        skill_role=skill.role,
        skill_source=skill.source,
        status=payload.status,
        input_summary=payload.input_summary.strip() if payload.input_summary else None,
        output_summary=payload.output_summary.strip() if payload.output_summary else None,
        started_at=payload.started_at or now,
        finished_at=payload.finished_at or now if payload.status in {"success", "failed", "blocked"} else None,
        created_by=current_user.id,
    )
    db.add(skill_run)
    db.flush()
    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            action="skill_run.create",
            target_type="skill_run",
            target_id=skill_run.id,
            metadata_={"demand_id": str(demand_id), "workflow_id": str(workflow.id), "stage": stage.stage_key, "skill_key": skill.key},
        )
    )
    db.commit()
    db.refresh(skill_run)
    return _serialize_skill_run(skill_run)


@router.get("/{demand_id}/workflows/{workflow_id}/current-stage-session", dependencies=[Depends(require_permissions("stage_session:view"))])
def get_current_stage_session(
    demand_id: UUID,
    workflow_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    demand = _get_demand_with_permission(demand_id, current_user, db)
    workflow = _get_workflow_for_demand(demand_id, workflow_id, db)
    stage = next((item for item in workflow.stages if item.status in {"current", "blocked"}), None)
    if not stage and workflow.stages:
        stage = workflow.stages[-1]
    if not stage:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="当前工作流没有阶段")
    skill = _stage_default_skill(db, workflow, stage)
    workspace = ensure_demand_workspace(db, demand, current_user)
    file_path = stage_file_path(stage.stage_key)
    file_content = read_workspace_file(workspace, file_path)
    session = db.scalar(
        select(StageSession)
        .where(StageSession.demand_id == demand_id)
        .where(StageSession.workflow_id == workflow_id)
        .where(StageSession.workflow_stage_id == stage.id)
        .order_by(StageSession.created_at.desc())
    )
    if not session:
        session = StageSession(
            demand_id=demand_id,
            workflow_id=workflow_id,
            workflow_stage_id=stage.id,
            stage=stage.stage_key,
            skill_key=skill.key,
            skill_name=skill.name,
            status="active",
            draft_title=file_path,
            draft_type=_artifact_type_by_stage(stage.stage_key),
            draft_content=file_content or f"# {stage.stage_name}产物草稿\n\n## 需求\n{demand.title}\n\n## 阶段目标\n{stage.stage_name}\n",
            created_by=current_user.id,
        )
        db.add(session)
        db.flush()
        db.add(
            StageMessage(
                session_id=session.id,
                role="assistant",
                content=f"已进入「{stage.stage_name}」阶段。我会使用「{skill.name}」协助你完成阶段产物，确认后会自动推进到下一阶段。",
            )
        )
        write_workspace_file(workspace, file_path, session.draft_content or "")
        db.commit()
        db.refresh(session)
    else:
        if file_content:
            session.draft_title = file_path
            session.draft_content = file_content
            db.commit()
    messages = db.scalars(
        select(StageMessage)
        .where(StageMessage.session_id == session.id)
        .order_by(StageMessage.created_at.asc())
    ).all()
    return _serialize_stage_session(session, messages)


@router.post("/stage-sessions/{session_id}/messages", dependencies=[Depends(require_permissions("stage_session:message"))])
def send_stage_session_message(
    session_id: UUID,
    payload: StageMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    session = db.get(StageSession, session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="阶段会话不存在")
    demand = _get_demand_with_permission(session.demand_id, current_user, db)
    workflow = _get_workflow_for_demand(session.demand_id, session.workflow_id, db)
    stage = _get_stage_for_workflow(workflow, session.stage, session.workflow_stage_id)
    skill = db.scalar(select(Skill).where(Skill.key == session.skill_key))
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill 不存在")
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="消息内容不能为空")

    db.add(StageMessage(session_id=session.id, role="user", content=content))
    reply, draft = _mock_ai_reply(demand, workflow, stage, skill, content)
    db.add(StageMessage(session_id=session.id, role="assistant", content=reply))
    session.draft_content = draft
    session.draft_title = stage_file_path(stage.stage_key)
    session.status = "active"
    workspace = ensure_demand_workspace(db, demand, current_user)
    write_workspace_file(workspace, stage_file_path(stage.stage_key), draft)
    db.commit()
    db.refresh(session)
    messages = db.scalars(
        select(StageMessage)
        .where(StageMessage.session_id == session.id)
        .order_by(StageMessage.created_at.asc())
    ).all()
    return _serialize_stage_session(session, messages)


@router.post("/stage-sessions/{session_id}/messages/stream", dependencies=[Depends(require_permissions("stage_session:message"))])
async def stream_stage_session_message(
    session_id: UUID,
    payload: StageMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    session = db.get(StageSession, session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="阶段会话不存在")
    demand = _get_demand_with_permission(session.demand_id, current_user, db)
    workflow = _get_workflow_for_demand(session.demand_id, session.workflow_id, db)
    stage = _get_stage_for_workflow(workflow, session.stage, session.workflow_stage_id)
    skill = db.scalar(select(Skill).where(Skill.key == session.skill_key))
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill 不存在")
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="消息内容不能为空")
    provider = snapshot_model_provider(_default_model_provider(db, current_user))
    workspace = ensure_demand_workspace(db, demand, current_user)
    system_prompt, user_prompt = await _build_stage_prompts(db, demand, workflow, stage, skill, workspace, content)
    session_id_value = session.id
    stage_key = stage.stage_key
    stage_file = stage_file_path(stage_key)
    workspace_root_path = workspace.root_path
    command_text = _extract_command(content)
    command_id_value: UUID | None = None

    db.add(StageMessage(session_id=session_id_value, role="user", content=content))
    if command_text:
        command = StageCommand(
            session_id=session_id_value,
            command=command_text,
            prompt=content,
            status="running",
            created_by=current_user.id,
        )
        db.add(command)
        db.flush()
        command_id_value = command.id
    db.add(
        StageToolCall(
            session_id=session_id_value,
            tool_name="read_skill_instruction",
            input_summary=f"{skill.key}/{skill.entry_file or 'SKILL.md'}",
            output_summary="已读取并注入当前阶段 Skill 指令",
            status="success",
            created_by=current_user.id,
        )
    )
    db.add(
        StageToolCall(
            session_id=session_id_value,
            tool_name="read_workspace_context",
            input_summary=".opendevflow/context.md, .opendevflow/stages.yml, .opendevflow/skills.yml",
            output_summary="已读取工作空间上下文",
            status="success",
            created_by=current_user.id,
        )
    )
    session.status = "active"
    db.commit()

    async def event_stream():
        chunks: list[str] = []
        try:
            yield _sse_event("start", {"session_id": str(session_id_value)})
            async for chunk in stream_chat_completion(provider, system_prompt, user_prompt):
                chunks.append(chunk)
                yield _sse_event("delta", {"content": chunk})
            reply = "".join(chunks).strip()
            if not reply:
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="模型未返回内容")

            with SessionLocal() as update_db:
                session_for_update = update_db.get(StageSession, session_id_value)
                if not session_for_update:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="阶段会话不存在")
                update_db.add(StageMessage(session_id=session_id_value, role="assistant", content=reply))
                artifact_content = _extract_artifact_content(reply)
                session_for_update.draft_title = stage_file
                session_for_update.draft_type = _artifact_type_by_stage(stage_key)
                session_for_update.status = "active"
                if artifact_content is not None:
                    session_for_update.draft_content = artifact_content
                    write_workspace_file(SimpleNamespace(root_path=workspace_root_path), stage_file, artifact_content)
                    update_db.add(
                        StageToolCall(
                            session_id=session_id_value,
                            tool_name="write_stage_artifact_file",
                            input_summary=stage_file,
                            output_summary=f"已写入 {len(artifact_content)} 字符",
                            status="success",
                            created_by=session_for_update.created_by,
                        )
                    )
                else:
                    update_db.add(
                        StageToolCall(
                            session_id=session_id_value,
                            tool_name="skip_stage_artifact_file",
                            input_summary=stage_file,
                            output_summary="AI 回复未包含明确产物块，已仅保存为会话消息",
                            status="success",
                            created_by=session_for_update.created_by,
                        )
                    )
                if command_id_value:
                    command_for_update = update_db.get(StageCommand, command_id_value)
                    if command_for_update:
                        command_for_update.status = "success"
                        command_for_update.result_summary = reply[:1000]
                update_db.flush()
                messages = update_db.scalars(
                    select(StageMessage)
                    .where(StageMessage.session_id == session_id_value)
                    .order_by(StageMessage.created_at.asc())
                ).all()
                done_payload = _serialize_stage_session(session_for_update, messages)
                update_db.commit()
                yield _sse_event("done", done_payload)
        except HTTPException as exc:
            if command_id_value:
                with SessionLocal() as error_db:
                    command_for_update = error_db.get(StageCommand, command_id_value)
                    if command_for_update:
                        command_for_update.status = "failed"
                        command_for_update.result_summary = str(exc.detail)
                        error_db.commit()
            yield _sse_event("error", {"detail": exc.detail})
        except Exception as exc:
            logger.exception("AI stage session stream failed: session_id=%s", session_id_value)
            if command_id_value:
                with SessionLocal() as error_db:
                    command_for_update = error_db.get(StageCommand, command_id_value)
                    if command_for_update:
                        command_for_update.status = "failed"
                        command_for_update.result_summary = exc.__class__.__name__
                        error_db.commit()
            yield _sse_event("error", {"detail": f"AI 会话调用失败：{exc.__class__.__name__}"})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/stage-sessions/{session_id}/complete", dependencies=[Depends(require_permissions("stage_session:complete"))])
async def complete_stage_session(
    session_id: UUID,
    payload: StageSessionComplete,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    session = db.get(StageSession, session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="阶段会话不存在")
    _get_demand_with_permission(session.demand_id, current_user, db)
    workflow = _get_workflow_for_demand(session.demand_id, session.workflow_id, db)
    stage = _get_stage_for_workflow(workflow, session.stage, session.workflow_stage_id)
    skill = db.scalar(select(Skill).where(Skill.key == session.skill_key))
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill 不存在")
    if workflow.status not in {"running", "blocked"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前工作流不能完成阶段")

    workspace = ensure_demand_workspace(db, workflow.demand, current_user)
    file_path = stage_file_path(stage.stage_key)
    content = payload.artifact_content or session.draft_content or read_workspace_file(workspace, file_path) or ""
    write_workspace_file(workspace, file_path, content)
    title = (payload.artifact_title or session.draft_title or file_path).strip()
    artifact_type = payload.artifact_type or session.draft_type or _artifact_type_by_stage(stage.stage_key)
    now = utc_now()
    skill_instruction = await _load_skill_instruction(skill)
    gate = _run_gate_check(db, session, stage, content, current_user, skill_instruction)
    db.flush()
    if gate.status != "passed":
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{gate.summary}：{gate.details}",
        )

    skill_run = SkillRun(
        demand_id=session.demand_id,
        workflow_id=workflow.id,
        workflow_stage_id=stage.id,
        stage=stage.stage_key,
        skill_key=skill.key,
        skill_name=skill.name,
        skill_role=skill.role,
        skill_source=skill.source,
        status="success",
        input_summary="阶段 AI 会话",
        output_summary=content[:1000] if content else "阶段已完成",
        started_at=session.created_at,
        finished_at=now,
        created_by=current_user.id,
    )
    db.add(skill_run)
    _create_artifact_version(db, session, session.demand_id, workflow.id, stage, artifact_type, title, content, current_user)

    stages = list(workflow.stages)
    current_index = next((index for index, item in enumerate(stages) if item.id == stage.id), -1)
    next_stage = stages[current_index + 1] if current_index >= 0 and current_index + 1 < len(stages) else None
    stage.status = "passed"
    stage.finished_at = now
    if next_stage:
        next_stage.status = "current"
        next_stage.started_at = now
        workflow.current_stage = next_stage.stage_key
        workflow.status = "running"
        message = f"阶段「{stage.stage_name}」已完成，已进入「{next_stage.stage_name}」"
    else:
        workflow.status = "done"
        message = f"阶段「{stage.stage_name}」已完成，工作流已结束"
    workflow.updated_at = now
    session.status = "completed"
    session.completed_at = now
    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            action="stage_session.complete",
            target_type="stage_session",
            target_id=session.id,
            metadata_={"workflow_id": str(workflow.id), "stage": stage.stage_key},
        )
    )
    db.commit()
    return {"message": message}


@router.get("/{demand_id}/stage-artifacts", dependencies=[Depends(require_permissions("artifact:view"))])
def list_stage_artifacts(
    demand_id: UUID,
    workflow_id: UUID | None = None,
    stage: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    _get_demand_with_permission(demand_id, current_user, db)
    query = select(WorkflowArtifact).where(WorkflowArtifact.demand_id == demand_id)
    if workflow_id:
        query = query.where(WorkflowArtifact.workflow_id == workflow_id)
    if stage:
        query = query.where(WorkflowArtifact.stage == stage)
    query = query.order_by(WorkflowArtifact.is_current.desc(), WorkflowArtifact.created_at.desc())
    return {"items": [_serialize_artifact(item) for item in db.scalars(query).all()]}


@router.get("/stage-sessions/{session_id}/gate-checks", dependencies=[Depends(require_permissions("stage_gate:view"))])
def list_stage_gate_checks(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    session = db.get(StageSession, session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="阶段会话不存在")
    _get_demand_with_permission(session.demand_id, current_user, db)
    items = db.scalars(
        select(StageGateCheck)
        .where(StageGateCheck.session_id == session_id)
        .order_by(StageGateCheck.created_at.desc())
    ).all()
    return {"items": [_serialize_gate_check(item) for item in items]}


@router.post("/stage-sessions/{session_id}/gate-checks", dependencies=[Depends(require_permissions("stage_gate:check"))])
async def check_stage_gate(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    session = db.get(StageSession, session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="阶段会话不存在")
    _get_demand_with_permission(session.demand_id, current_user, db)
    workflow = _get_workflow_for_demand(session.demand_id, session.workflow_id, db)
    stage = _get_stage_for_workflow(workflow, session.stage, session.workflow_stage_id)
    skill = db.scalar(select(Skill).where(Skill.key == session.skill_key))
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill 不存在")
    workspace = ensure_demand_workspace(db, workflow.demand, current_user)
    content = session.draft_content or read_workspace_file(workspace, stage_file_path(stage.stage_key)) or ""
    skill_instruction = await _load_skill_instruction(skill)
    gate = _run_gate_check(db, session, stage, content, current_user, skill_instruction)
    db.commit()
    db.refresh(gate)
    return _serialize_gate_check(gate)


@router.get("/stage-sessions/{session_id}/commands", dependencies=[Depends(require_permissions("stage_command:view"))])
def list_stage_commands(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    session = db.get(StageSession, session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="阶段会话不存在")
    _get_demand_with_permission(session.demand_id, current_user, db)
    items = db.scalars(
        select(StageCommand)
        .where(StageCommand.session_id == session_id)
        .order_by(StageCommand.created_at.desc())
    ).all()
    return {"items": [_serialize_stage_command(item) for item in items]}


@router.get("/stage-sessions/{session_id}/tool-calls", dependencies=[Depends(require_permissions("stage_tool:view"))])
def list_stage_tool_calls(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    session = db.get(StageSession, session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="阶段会话不存在")
    _get_demand_with_permission(session.demand_id, current_user, db)
    items = db.scalars(
        select(StageToolCall)
        .where(StageToolCall.session_id == session_id)
        .order_by(StageToolCall.created_at.desc())
    ).all()
    return {"items": [_serialize_tool_call(item) for item in items]}


@router.post("/{demand_id}/stage-artifacts", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permissions("artifact:create"))])
def create_stage_artifact(
    demand_id: UUID,
    payload: ArtifactCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    _get_demand_with_permission(demand_id, current_user, db)
    workflow = _get_workflow_for_demand(demand_id, payload.workflow_id, db)
    stage = _get_stage_for_workflow(workflow, payload.stage, payload.workflow_stage_id)
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="产物标题不能为空")
    artifact = WorkflowArtifact(
        demand_id=demand_id,
        workflow_id=workflow.id,
        workflow_stage_id=stage.id,
        stage=stage.stage_key,
        artifact_type=payload.artifact_type,
        title=title,
        content=payload.content,
        version=1,
        version_no=1,
        is_current=True,
        created_by=current_user.id,
    )
    db.add(artifact)
    db.flush()
    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            action="artifact.create",
            target_type="workflow_artifact",
            target_id=artifact.id,
            metadata_={"demand_id": str(demand_id), "workflow_id": str(workflow.id), "stage": stage.stage_key, "artifact_type": artifact.artifact_type},
        )
    )
    db.commit()
    db.refresh(artifact)
    return _serialize_artifact(artifact)


@router.patch("/{demand_id}/stage-artifacts/{artifact_id}", dependencies=[Depends(require_permissions("artifact:update"))])
def update_stage_artifact(
    demand_id: UUID,
    artifact_id: UUID,
    payload: ArtifactUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    _get_demand_with_permission(demand_id, current_user, db)
    artifact = db.get(WorkflowArtifact, artifact_id)
    if not artifact or artifact.demand_id != demand_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="阶段产物不存在")
    artifact_type = payload.artifact_type if payload.artifact_type is not None else artifact.artifact_type
    title = artifact.title
    if payload.title is not None:
        title = payload.title.strip()
        if not title:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="产物标题不能为空")
    content = payload.content if payload.content is not None else artifact.content
    stage = _get_stage_for_workflow(artifact.workflow, artifact.stage, artifact.workflow_stage_id)
    artifact.is_current = False
    new_artifact = _create_artifact_version(
        db,
        None,
        artifact.demand_id,
        artifact.workflow_id,
        stage,
        artifact_type,
        title,
        content,
        current_user,
    )
    new_artifact.source_session_id = artifact.source_session_id
    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            action="artifact.update",
            target_type="workflow_artifact",
            target_id=new_artifact.id,
            metadata_={"demand_id": str(demand_id), "artifact_type": new_artifact.artifact_type, "previous_artifact_id": str(artifact.id)},
        )
    )
    db.commit()
    db.refresh(new_artifact)
    return _serialize_artifact(new_artifact)
