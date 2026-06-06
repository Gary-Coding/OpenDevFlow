"""Agent Run 模型"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import String, Text, ForeignKey, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import UUIDTimestampMixin


class AgentRun(UUIDTimestampMixin, Base):
    """Agent Run 记录模型"""
    __tablename__ = "agent_runs"

    demand_id: Mapped[UUID] = mapped_column(ForeignKey("demands.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_id: Mapped[UUID] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(50), nullable=False)  # 所属阶段
    # agent 类型: manual, claude_code, codex_cli, other
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    # 状态: pending, running, success, failed, blocked
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    input_summary: Mapped[str | None] = mapped_column(Text)
    output_summary: Mapped[str | None] = mapped_column(Text)
    logs: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    exit_code: Mapped[int | None] = mapped_column(Integer)
    blocker_reason: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)

    # 关联
    demand: Mapped["Demand"] = relationship("Demand", lazy="selectin")
    workflow: Mapped["Workflow"] = relationship("Workflow", lazy="selectin")
    creator: Mapped["User"] = relationship("User", lazy="selectin")
