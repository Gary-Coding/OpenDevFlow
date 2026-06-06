"""组织模型：公司和组织架构"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import String, Integer, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import UUIDTimestampMixin


class Company(UUIDTimestampMixin, Base):
    """公司模型"""
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    # 关联
    departments: Mapped[list["Department"]] = relationship(
        "Department", back_populates="company", lazy="selectin"
    )


class Department(UUIDTimestampMixin, Base):
    """组织架构模型，兼容原 departments 表；org_type 区分部门、项目组和开发组。"""
    __tablename__ = "departments"

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_id: Mapped[UUID | None] = mapped_column(ForeignKey("departments.id", ondelete="CASCADE"), index=True)
    ancestors: Mapped[str] = mapped_column(Text, nullable=False, default="")  # 祖先部门ID路径，逗号分隔
    org_type: Mapped[str] = mapped_column(String(30), nullable=False, default="department")
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    order_num: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    # 关联
    company: Mapped["Company"] = relationship("Company", back_populates="departments", lazy="selectin")
    parent: Mapped["Department | None"] = relationship("Department", remote_side="Department.id", lazy="selectin")
    members: Mapped[list["OrganizationMember"]] = relationship(
        "OrganizationMember", back_populates="department", cascade="all, delete-orphan", lazy="selectin"
    )


class OrganizationMember(UUIDTimestampMixin, Base):
    """组织架构成员关系，用于表达跨组成员和组长。"""
    __tablename__ = "organization_members"
    __table_args__ = (
        UniqueConstraint("department_id", "user_id", name="uq_organization_members_department_user"),
    )

    department_id: Mapped[UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    member_role: Mapped[str] = mapped_column(String(20), nullable=False, default="member")

    department: Mapped["Department"] = relationship("Department", back_populates="members", lazy="selectin")
    user: Mapped["User"] = relationship("User", lazy="selectin")
