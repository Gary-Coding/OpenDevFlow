"""代码上下文快照模型。"""
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import UUIDTimestampMixin


class CodeContextSnapshot(UUIDTimestampMixin, Base):
    """需求维度的代码上下文快照。来源可以是 Bridge、Git 或云端 workspace。"""
    __tablename__ = "code_context_snapshots"

    demand_id: Mapped[UUID] = mapped_column(ForeignKey("demands.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False, default="bridge", index=True)
    source_ref: Mapped[str | None] = mapped_column(Text)
    root_path: Mapped[str | None] = mapped_column(Text)
    project_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    snapshot_content: Mapped[str] = mapped_column(Text, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)

    demand: Mapped["Demand"] = relationship("Demand", lazy="selectin")
    creator: Mapped["User"] = relationship("User", lazy="selectin")


class CodeContextScanResult(UUIDTimestampMixin, Base):
    """Bridge 扫描出的候选项目结果，用户确认后才生成当前代码上下文。"""
    __tablename__ = "code_context_scan_results"

    demand_id: Mapped[UUID] = mapped_column(ForeignKey("demands.id", ondelete="CASCADE"), nullable=False, index=True)
    bridge_client_id: Mapped[UUID | None] = mapped_column(ForeignKey("local_bridge_clients.id", ondelete="SET NULL"), index=True)
    source_ref: Mapped[str | None] = mapped_column(Text)
    root_path: Mapped[str | None] = mapped_column(Text)
    project_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    snapshot_content: Mapped[str] = mapped_column(Text, nullable=False)
    projects_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)

    demand: Mapped["Demand"] = relationship("Demand", lazy="selectin")
    bridge_client: Mapped["LocalBridgeClient | None"] = relationship("LocalBridgeClient", lazy="selectin")
    creator: Mapped["User"] = relationship("User", lazy="selectin")
