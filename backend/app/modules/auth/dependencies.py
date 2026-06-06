from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.user import User


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


@dataclass
class CurrentUser:
    id: str
    roles: list[str]
    permissions: list[str]
    menus: list[dict] | None = None
    username: str | None = None
    display_name: str | None = None


def get_current_user(token: str = Depends(oauth2_scheme)) -> CurrentUser:
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        subject = payload.get("sub")
        roles = payload.get("roles", [])
        permissions = payload.get("permissions", [])
        menus = payload.get("menus", [])
        username = payload.get("username")
        display_name = payload.get("display_name")
        if not subject:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        return CurrentUser(
            id=subject,
            roles=roles,
            permissions=permissions,
            menus=menus,
            username=username,
            display_name=display_name,
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证信息无效，请重新登录",
        ) from exc


def get_current_orm_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    加载完整的 ORM User 对象，包含 roles、menus、company、department 等关联数据。
    用于需要数据权限的业务接口。
    """
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        subject = payload.get("sub")
        if not subject:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

        user_id = UUID(subject)
        user = db.query(User).filter(User.id == user_id).first()

        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在或已停用",
            )

        return user
    except (JWTError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证信息无效，请重新登录",
        ) from exc
