"""Review 模型"""
from uuid import UUID

from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import UUIDTimestampMixin


class Review(UUIDTimestampMixin, Base):
    """审查和 QA 记录模型"""
    __tablename__ = "reviews"

    demand_id: Mapped[UUID] = mapped_column(ForeignKey("demands.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_id: Mapped[UUID] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(50), nullable=False)  # 所属阶段
    # review 类型: product_review, spec_review, dev_review, qa_review, final_review
    review_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # 结果: passed, failed, blocked
    result: Mapped[str] = mapped_column(String(20), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)

    # 关联
    demand: Mapped["Demand"] = relationship("Demand", lazy="selectin")
    workflow: Mapped["Workflow"] = relationship("Workflow", lazy="selectin")
    creator: Mapped["User"] = relationship("User", lazy="selectin")
