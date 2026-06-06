"""Skill 元数据模型。"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import UUIDTimestampMixin


class Skill(UUIDTimestampMixin, Base):
    """平台可调用的 Skill 元数据。Skill 内容由 Git 仓库维护。"""
    __tablename__ = "skills"

    key: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False, default="0.1.0")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    git_url: Mapped[str | None] = mapped_column(Text)
    git_ref: Mapped[str | None] = mapped_column(String(120))
    sub_path: Mapped[str | None] = mapped_column(Text)
    entry_file: Mapped[str] = mapped_column(String(120), nullable=False, default="SKILL.md")
    checksum: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)


class WorkflowStageSkillBinding(UUIDTimestampMixin, Base):
    """一级工作流阶段和 Skill 的默认绑定关系。"""
    __tablename__ = "workflow_stage_skill_bindings"
    __table_args__ = (
        UniqueConstraint("template_key", "stage_key", "skill_key", name="uq_workflow_stage_skill_binding"),
    )

    template_key: Mapped[str] = mapped_column(String(50), nullable=False, default="full", index=True)
    stage_key: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    skill_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    order_num: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)


class SkillRun(UUIDTimestampMixin, Base):
    """一次平台 Skill 执行记录。由阶段推进自动生成，也保留 API 侧登记能力。"""
    __tablename__ = "skill_runs"

    demand_id: Mapped[UUID] = mapped_column(ForeignKey("demands.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_id: Mapped[UUID] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_stage_id: Mapped[UUID | None] = mapped_column(ForeignKey("workflow_stages.id", ondelete="SET NULL"), index=True)
    stage: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    skill_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    skill_name: Mapped[str] = mapped_column(String(120), nullable=False)
    skill_role: Mapped[str | None] = mapped_column(String(40))
    skill_source: Mapped[str | None] = mapped_column(String(40))
    # 状态: pending, running, success, failed, blocked
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="success", index=True)
    input_summary: Mapped[str | None] = mapped_column(Text)
    output_summary: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)

    demand: Mapped["Demand"] = relationship("Demand", lazy="selectin")
    workflow: Mapped["Workflow"] = relationship("Workflow", lazy="selectin")
    workflow_stage: Mapped["WorkflowStage | None"] = relationship("WorkflowStage", lazy="selectin")
    creator: Mapped["User"] = relationship("User", lazy="selectin")


class StageSession(UUIDTimestampMixin, Base):
    """工作流阶段 AI 会话。用于驱动阶段澄清、产物草稿和阶段完成。"""
    __tablename__ = "stage_sessions"

    demand_id: Mapped[UUID] = mapped_column(ForeignKey("demands.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_id: Mapped[UUID] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_stage_id: Mapped[UUID] = mapped_column(ForeignKey("workflow_stages.id", ondelete="CASCADE"), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    skill_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    skill_name: Mapped[str] = mapped_column(String(120), nullable=False)
    # 状态: active, waiting_review, completed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    draft_title: Mapped[str | None] = mapped_column(String(255))
    draft_type: Mapped[str | None] = mapped_column(String(50))
    draft_content: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    demand: Mapped["Demand"] = relationship("Demand", lazy="selectin")
    workflow: Mapped["Workflow"] = relationship("Workflow", lazy="selectin")
    workflow_stage: Mapped["WorkflowStage"] = relationship("WorkflowStage", lazy="selectin")
    creator: Mapped["User"] = relationship("User", lazy="selectin")


class StageMessage(UUIDTimestampMixin, Base):
    """阶段会话消息。"""
    __tablename__ = "stage_messages"

    session_id: Mapped[UUID] = mapped_column(ForeignKey("stage_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    session: Mapped["StageSession"] = relationship("StageSession", lazy="selectin")


class StageGateCheck(UUIDTimestampMixin, Base):
    """阶段 Gate 校验记录。"""
    __tablename__ = "stage_gate_checks"

    session_id: Mapped[UUID] = mapped_column(ForeignKey("stage_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    demand_id: Mapped[UUID] = mapped_column(ForeignKey("demands.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_id: Mapped[UUID] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_stage_id: Mapped[UUID] = mapped_column(ForeignKey("workflow_stages.id", ondelete="CASCADE"), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    details: Mapped[str | None] = mapped_column(Text)
    checked_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)

    session: Mapped["StageSession"] = relationship("StageSession", lazy="selectin")


class StageCommand(UUIDTimestampMixin, Base):
    """阶段快捷命令执行记录。"""
    __tablename__ = "stage_commands"

    session_id: Mapped[UUID] = mapped_column(ForeignKey("stage_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    command: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running", index=True)
    result_summary: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)

    session: Mapped["StageSession"] = relationship("StageSession", lazy="selectin")


class StageToolCall(UUIDTimestampMixin, Base):
    """阶段 AI 工具调用记录。当前先记录平台自动执行的安全工具。"""
    __tablename__ = "stage_tool_calls"

    session_id: Mapped[UUID] = mapped_column(ForeignKey("stage_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    tool_name: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    input_summary: Mapped[str | None] = mapped_column(Text)
    output_summary: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="success", index=True)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)

    session: Mapped["StageSession"] = relationship("StageSession", lazy="selectin")
