from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Integer, String, Table, Column, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import UUIDTimestampMixin


user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id"), primary_key=True),
    Column("role_id", ForeignKey("roles.id"), primary_key=True),
)

role_menus = Table(
    "role_menus",
    Base.metadata,
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("menu_id", ForeignKey("menus.id", ondelete="CASCADE"), primary_key=True),
)

role_departments = Table(
    "role_departments",
    Base.metadata,
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("department_id", ForeignKey("departments.id", ondelete="CASCADE"), primary_key=True),
)


class User(UUIDTimestampMixin, Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # 组织归属
    company_id: Mapped[UUID | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"), index=True)
    department_id: Mapped[UUID | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), index=True)

    roles: Mapped[list["Role"]] = relationship(
        secondary=user_roles, back_populates="users", lazy="selectin"
    )
    company: Mapped["Company | None"] = relationship("Company", lazy="selectin")
    department: Mapped["Department | None"] = relationship("Department", lazy="selectin")
    organization_members: Mapped[list["OrganizationMember"]] = relationship(
        "OrganizationMember", back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )


class Role(UUIDTimestampMixin, Base):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(String(255))
    # 数据范围：all, custom_dept, dept, dept_and_child, self
    data_scope: Mapped[str] = mapped_column(String(20), nullable=False, default="self")

    users: Mapped[list[User]] = relationship(
        secondary=user_roles, back_populates="roles", lazy="selectin"
    )
    menus: Mapped[list["Menu"]] = relationship(
        secondary=role_menus, back_populates="roles", lazy="selectin"
    )
    custom_departments: Mapped[list["Department"]] = relationship(
        secondary=role_departments, lazy="selectin"
    )


class Menu(UUIDTimestampMixin, Base):
    __tablename__ = "menus"

    parent_id: Mapped[UUID | None] = mapped_column(ForeignKey("menus.id", ondelete="CASCADE"), index=True)
    menu_name: Mapped[str] = mapped_column(String(120), nullable=False)
    menu_type: Mapped[str] = mapped_column(String(1), nullable=False)
    path: Mapped[str | None] = mapped_column(String(255))
    component: Mapped[str | None] = mapped_column(String(255))
    permission: Mapped[str | None] = mapped_column(String(120), index=True)
    icon: Mapped[str | None] = mapped_column(String(80))
    order_num: Mapped[int] = mapped_column(Integer, default=0)
    visible: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    parent: Mapped["Menu | None"] = relationship("Menu", remote_side="Menu.id", lazy="selectin")
    roles: Mapped[list[Role]] = relationship(
        secondary=role_menus, back_populates="menus", lazy="selectin"
    )
