"""需求和工作流模型"""
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import String, Text, Date, ForeignKey, Integer, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import UUIDTimestampMixin


class Demand(UUIDTimestampMixin, Base):
    """需求模型"""
    __tablename__ = "demands"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    # 需求类型: new_business, new_project, optimization, bugfix, refactor
    type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    expected_live_at: Mapped[date | None] = mapped_column(Date)
    repository_id: Mapped[UUID | None] = mapped_column(ForeignKey("repositories.id", ondelete="SET NULL"))
    # 需求状态: active, blocked, delivered, archived
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)

    # 组织归属（用于数据权限）
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    department_id: Mapped[UUID] = mapped_column(ForeignKey("departments.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)

    # 关联
    repository: Mapped["Repository | None"] = relationship("Repository", lazy="selectin")
    company: Mapped["Company"] = relationship("Company", lazy="selectin")
    department: Mapped["Department"] = relationship("Department", lazy="selectin")
    creator: Mapped["User"] = relationship("User", lazy="selectin")
    workflows: Mapped[list["Workflow"]] = relationship(
        "Workflow",
        back_populates="demand",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="Workflow.created_at.desc()",
    )
    members: Mapped[list["DemandMember"]] = relationship(
        "DemandMember", back_populates="demand", cascade="all, delete-orphan", lazy="selectin"
    )
    workspace: Mapped["DemandWorkspace | None"] = relationship(
        "DemandWorkspace", back_populates="demand", cascade="all, delete-orphan", lazy="selectin"
    )


class DemandWorkspace(UUIDTimestampMixin, Base):
    """需求服务端工作空间。文件存储在挂载盘，数据库只保存空间元数据。"""
    __tablename__ = "demand_workspaces"

    demand_id: Mapped[UUID] = mapped_column(ForeignKey("demands.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    root_path: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)

    demand: Mapped["Demand"] = relationship("Demand", back_populates="workspace", lazy="selectin")
    creator: Mapped["User"] = relationship("User", lazy="selectin")


class DemandMember(UUIDTimestampMixin, Base):
    """需求成员关系，用于表达需求内产品、开发、测试等职责。"""
    __tablename__ = "demand_members"
    __table_args__ = (
        UniqueConstraint("demand_id", "user_id", name="uq_demand_members_demand_user"),
    )

    demand_id: Mapped[UUID] = mapped_column(ForeignKey("demands.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    member_role: Mapped[str] = mapped_column(String(30), nullable=False, default="viewer", index=True)

    demand: Mapped["Demand"] = relationship("Demand", back_populates="members", lazy="selectin")
    user: Mapped["User"] = relationship("User", lazy="selectin")


class Workflow(UUIDTimestampMixin, Base):
    """工作流模型"""
    __tablename__ = "workflows"

    demand_id: Mapped[UUID] = mapped_column(ForeignKey("demands.id", ondelete="CASCADE"), nullable=False, index=True)
    template_key: Mapped[str] = mapped_column(String(50), nullable=False, default="full", index=True)
    workflow_type: Mapped[str] = mapped_column(String(30), nullable=False, default="full", index=True)
    current_stage: Mapped[str] = mapped_column(String(50), nullable=False, default="demand_created")
    # 工作流状态: running, blocked, done, archived
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")

    # 关联
    demand: Mapped["Demand"] = relationship("Demand", back_populates="workflows", lazy="selectin")
    stages: Mapped[list["WorkflowStage"]] = relationship(
        "WorkflowStage",
        back_populates="workflow",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="WorkflowStage.sort_order",
    )


class WorkflowStage(UUIDTimestampMixin, Base):
    """工作流阶段模型"""
    __tablename__ = "workflow_stages"

    workflow_id: Mapped[UUID] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    stage_key: Mapped[str] = mapped_column(String(50), nullable=False)  # demand_created, product_discovery, etc.
    stage_name: Mapped[str] = mapped_column(String(120), nullable=False)  # 需求已创建, 需求澄清, etc.
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    # 阶段状态: pending, current, passed, blocked, skipped
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    blocked_reason: Mapped[str | None] = mapped_column(Text)

    # 关联
    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="stages", lazy="selectin")


class WorkflowTemplate(UUIDTimestampMixin, Base):
    """工作流模板。用于按需求类型生成不同阶段链路。"""
    __tablename__ = "workflow_templates"

    key: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    workflow_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    order_num: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    stages: Mapped[list["WorkflowTemplateStage"]] = relationship(
        "WorkflowTemplateStage",
        back_populates="template",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="WorkflowTemplateStage.sort_order",
    )


class WorkflowTemplateStage(UUIDTimestampMixin, Base):
    """工作流模板阶段。"""
    __tablename__ = "workflow_template_stages"
    __table_args__ = (
        UniqueConstraint("template_key", "stage_key", name="uq_workflow_template_stage"),
    )

    template_key: Mapped[str] = mapped_column(String(50), ForeignKey("workflow_templates.key", ondelete="CASCADE"), nullable=False, index=True)
    stage_key: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    stage_name: Mapped[str] = mapped_column(String(120), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)

    template: Mapped["WorkflowTemplate"] = relationship("WorkflowTemplate", back_populates="stages", lazy="selectin")
