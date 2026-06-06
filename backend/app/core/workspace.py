"""需求工作空间文件服务。"""
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.demand import Demand, DemandWorkspace, Workflow
from app.models.skill import Skill, WorkflowStageSkillBinding
from app.models.user import User


DEFAULT_STAGE_FILES = {
    "demand_planning": "docs/prd.md",
    "product_design": "openspec/design.md",
    "development": "delivery/dev-plan.md",
    "acceptance_review": "qa/test-plan.md",
    "issue_confirm": "docs/acceptance-criteria.md",
    "fix_implementation": "delivery/dev-plan.md",
    "regression_verify": "qa/test-plan.md",
    "change_confirm": "docs/acceptance-criteria.md",
    "self_test": "delivery/self-test.md",
    "delivery_archive": "delivery/summary.md",
}

BASIC_WORKSPACE_FILES = {
    ".opendevflow/workspace.yml": "version: 1\n",
    ".opendevflow/stages.yml": "stages: []\n",
    ".opendevflow/skills.yml": "skills: {}\n",
    ".opendevflow/context.md": "# 需求上下文\n\n",
}

STAGE_FILE_TEMPLATES = {
    "docs/prd.md": "# PRD\n\n",
    "docs/user-stories.md": "# 用户故事\n\n",
    "docs/acceptance-criteria.md": "# 验收标准\n\n",
    "openspec/proposal.md": "# OpenSpec Proposal\n\n",
    "openspec/design.md": "# OpenSpec Design\n\n",
    "openspec/tasks.md": "# OpenSpec Tasks\n\n",
    "delivery/dev-plan.md": "# 开发计划\n\n",
    "delivery/implementation-notes.md": "# 实施记录\n\n",
    "delivery/self-test.md": "# 自测记录\n\n",
    "delivery/summary.md": "# 交付总结\n\n",
    "qa/test-plan.md": "# 测试计划\n\n",
    "qa/test-cases.md": "# 测试用例\n\n",
    "qa/defects.md": "# 缺陷记录\n\n",
    "qa/acceptance-report.md": "# 验收结论\n\n",
    "chat/stage-session.md": "# 阶段会话\n\n",
}


def workspace_root() -> Path:
    root = Path(settings.workspace_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def demand_workspace_relative_path(company_id: UUID, demand_id: UUID) -> str:
    return f"companies/{company_id}/demands/{demand_id}"


def ensure_demand_workspace(db: Session, demand: Demand, current_user: User) -> DemandWorkspace:
    workspace = db.scalar(select(DemandWorkspace).where(DemandWorkspace.demand_id == demand.id))
    if workspace:
        ensure_workspace_files(Path(workspace.root_path))
        return workspace

    root_path = workspace_root() / demand_workspace_relative_path(demand.company_id, demand.id)
    ensure_workspace_files(root_path)
    workspace = DemandWorkspace(
        demand_id=demand.id,
        company_id=demand.company_id,
        root_path=str(root_path),
        status="active",
        created_by=current_user.id,
    )
    db.add(workspace)
    db.flush()
    return workspace


def ensure_workspace_files(root_path: Path) -> None:
    ensure_base_workspace_files(root_path)


def ensure_base_workspace_files(root_path: Path) -> None:
    root_path.mkdir(parents=True, exist_ok=True)
    for relative_path, content in BASIC_WORKSPACE_FILES.items():
        file_path = root_path / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        if not file_path.exists():
            file_path.write_text(content, encoding="utf-8")


def ensure_workflow_stage_files(workspace: DemandWorkspace, workflow: Workflow) -> None:
    root_path = Path(workspace.root_path).expanduser().resolve()
    ensure_base_workspace_files(root_path)
    for stage in workflow.stages:
        relative_path = stage_file_path(stage.stage_key)
        content = STAGE_FILE_TEMPLATES.get(relative_path, f"# {stage.stage_name}\n\n")
        file_path = root_path / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        if not file_path.exists():
            file_path.write_text(content, encoding="utf-8")


def safe_workspace_file(root_path: str, relative_path: str) -> Path:
    if not relative_path or relative_path.startswith("/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件路径不合法")
    root = Path(root_path).expanduser().resolve()
    file_path = (root / relative_path).resolve()
    if root != file_path and root not in file_path.parents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件路径越界")
    return file_path


def read_workspace_file(workspace: DemandWorkspace, relative_path: str) -> str:
    file_path = safe_workspace_file(workspace.root_path, relative_path)
    if not file_path.exists():
        return ""
    if not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="目标不是文件")
    return file_path.read_text(encoding="utf-8")


def write_workspace_file(workspace: DemandWorkspace, relative_path: str, content: str) -> None:
    file_path = safe_workspace_file(workspace.root_path, relative_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")


def list_workspace_files(workspace: DemandWorkspace) -> list[dict]:
    root = Path(workspace.root_path).expanduser().resolve()
    if not root.exists():
        ensure_base_workspace_files(root)
    items = []
    for file_path in sorted(root.rglob("*")):
        if not file_path.is_file():
            continue
        relative_path = file_path.relative_to(root).as_posix()
        items.append(
            {
                "path": relative_path,
                "name": file_path.name,
                "size": file_path.stat().st_size,
            }
        )
    return items


def stage_file_path(stage_key: str) -> str:
    return DEFAULT_STAGE_FILES.get(stage_key, "docs/prd.md")


def write_workspace_workflow_metadata(db: Session, workspace: DemandWorkspace, workflow: Workflow) -> None:
    ensure_workflow_stage_files(workspace, workflow)
    stages_lines = ["stages:"]
    for stage in workflow.stages:
        stages_lines.extend(
            [
                f"  - key: {stage.stage_key}",
                f"    name: {stage.stage_name}",
                f"    status: {stage.status}",
                f"    file: {stage_file_path(stage.stage_key)}",
            ]
        )
    write_workspace_file(workspace, ".opendevflow/stages.yml", "\n".join(stages_lines) + "\n")

    bindings = db.scalars(
        select(WorkflowStageSkillBinding)
        .where(WorkflowStageSkillBinding.template_key == workflow.template_key)
        .where(WorkflowStageSkillBinding.status == "active")
        .order_by(WorkflowStageSkillBinding.stage_key.asc(), WorkflowStageSkillBinding.order_num.asc())
    ).all()
    skill_keys = [binding.skill_key for binding in bindings]
    skills = db.scalars(select(Skill).where(Skill.key.in_(skill_keys))).all() if skill_keys else []
    skill_by_key = {skill.key: skill for skill in skills}
    skill_lines = [f"template: {workflow.template_key}", "skills:"]
    for binding in bindings:
        skill = skill_by_key.get(binding.skill_key)
        if not skill:
            continue
        skill_lines.extend(
            [
                f"  - stage: {binding.stage_key}",
                f"    key: {skill.key}",
                f"    name: {skill.name}",
                f"    role: {skill.role}",
                f"    source: {skill.source}",
                f"    default: {str(binding.is_default).lower()}",
            ]
        )
    write_workspace_file(workspace, ".opendevflow/skills.yml", "\n".join(skill_lines) + "\n")
