"""本地 Bridge 与多项目工作区模型。"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import UUIDTimestampMixin


class LocalBridgeClient(UUIDTimestampMixin, Base):
    """用户本地 Bridge 连接登记。"""
    __tablename__ = "local_bridge_clients"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    client_name: Mapped[str] = mapped_column(String(120), nullable=False)
    client_key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="offline", index=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_: Mapped[str | None] = mapped_column("metadata", Text)

    user: Mapped["User"] = relationship("User", lazy="selectin")


class DemandLocalProject(UUIDTimestampMixin, Base):
    """需求绑定的本地代码项目。一个需求可关联多个微服务项目。"""
    __tablename__ = "demand_local_projects"
    __table_args__ = (
        UniqueConstraint("demand_id", "project_key", name="uq_demand_local_project_key"),
    )

    demand_id: Mapped[UUID] = mapped_column(ForeignKey("demands.id", ondelete="CASCADE"), nullable=False, index=True)
    bridge_client_id: Mapped[UUID | None] = mapped_column(ForeignKey("local_bridge_clients.id", ondelete="SET NULL"), index=True)
    project_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    project_name: Mapped[str] = mapped_column(String(120), nullable=False)
    local_path: Mapped[str] = mapped_column(Text, nullable=False)
    project_type: Mapped[str] = mapped_column(String(50), nullable=False, default="service", index=True)
    branch_name: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    order_num: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)

    demand: Mapped["Demand"] = relationship("Demand", lazy="selectin")
    bridge_client: Mapped["LocalBridgeClient | None"] = relationship("LocalBridgeClient", lazy="selectin")
    creator: Mapped["User"] = relationship("User", lazy="selectin")


class LocalBridgeCommand(UUIDTimestampMixin, Base):
    """平台下发给本地 Bridge 的命令请求记录。"""
    __tablename__ = "local_bridge_commands"

    demand_id: Mapped[UUID] = mapped_column(ForeignKey("demands.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_id: Mapped[UUID | None] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"), index=True)
    local_project_id: Mapped[UUID | None] = mapped_column(ForeignKey("demand_local_projects.id", ondelete="SET NULL"), index=True)
    bridge_client_id: Mapped[UUID | None] = mapped_column(ForeignKey("local_bridge_clients.id", ondelete="SET NULL"), index=True)
    command_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    command_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    logs: Mapped[str | None] = mapped_column(Text)
    output_summary: Mapped[str | None] = mapped_column(Text)
    exit_code: Mapped[int | None] = mapped_column(Integer)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)

    demand: Mapped["Demand"] = relationship("Demand", lazy="selectin")
    local_project: Mapped["DemandLocalProject | None"] = relationship("DemandLocalProject", lazy="selectin")
    bridge_client: Mapped["LocalBridgeClient | None"] = relationship("LocalBridgeClient", lazy="selectin")
    creator: Mapped["User"] = relationship("User", lazy="selectin")
