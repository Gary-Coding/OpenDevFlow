"""工作流产物模型"""
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import UUIDTimestampMixin


class WorkflowArtifact(UUIDTimestampMixin, Base):
    """工作流产物模型"""
    __tablename__ = "workflow_artifacts"

    demand_id: Mapped[UUID] = mapped_column(ForeignKey("demands.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_id: Mapped[UUID] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_stage_id: Mapped[UUID | None] = mapped_column(ForeignKey("workflow_stages.id", ondelete="SET NULL"), index=True)
    stage: Mapped[str] = mapped_column(String(50), nullable=False)  # 所属阶段
    # artifact 类型: prd, user_stories, acceptance_criteria, proposal, design, tasks, dev_plan, etc.
    artifact_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")  # Markdown 内容
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    source_session_id: Mapped[UUID | None] = mapped_column(ForeignKey("stage_sessions.id", ondelete="SET NULL"), index=True)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)

    # 关联
    demand: Mapped["Demand"] = relationship("Demand", lazy="selectin")
    workflow: Mapped["Workflow"] = relationship("Workflow", lazy="selectin")
    workflow_stage: Mapped["WorkflowStage | None"] = relationship("WorkflowStage", lazy="selectin")
    creator: Mapped["User"] = relationship("User", lazy="selectin")
