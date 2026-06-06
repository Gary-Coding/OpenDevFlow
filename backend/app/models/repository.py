"""仓库模型"""
from uuid import UUID

from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import UUIDTimestampMixin


class Repository(UUIDTimestampMixin, Base):
    """仓库模型"""
    __tablename__ = "repositories"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    git_url: Mapped[str | None] = mapped_column(Text)
    default_branch: Mapped[str] = mapped_column(String(80), nullable=False, default="main")
    local_path: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)

    # 关联
    creator: Mapped["User | None"] = relationship("User", lazy="selectin")
