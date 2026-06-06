from fastapi import Depends, HTTPException, status

from app.modules.auth.dependencies import CurrentUser, get_current_user


def _has_permission(user_permissions: set[str], code: str) -> bool:
    if code in user_permissions or "*:*:*" in user_permissions:
        return True
    parts = code.split(":")
    if len(parts) == 3:
        module, resource, action = parts
        return (
            f"{module}:*:*" in user_permissions
            or f"{module}:{resource}:*" in user_permissions
            or f"*:*:{action}" in user_permissions
        )
    return False


def require_roles(*allowed_roles: str):
    def dependency(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not set(current_user.roles).intersection(allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足",
            )
        return current_user

    return dependency


def require_permissions(*allowed_permissions: str):
    def dependency(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if "admin" in current_user.roles:
            return current_user
        user_permissions = set(current_user.permissions)
        if not any(_has_permission(user_permissions, permission) for permission in allowed_permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足",
            )
        return current_user

    return dependency
