from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import UUIDTimestampMixin


class ModelProvider(UUIDTimestampMixin, Base):
    """用户自带的大模型服务配置。API Key 加密保存，不向前端回显。"""
    __tablename__ = "model_providers"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_model_providers_user_name"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text)
    default_model: Mapped[str | None] = mapped_column(String(160))
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)

    user: Mapped["User"] = relationship("User", lazy="selectin")
