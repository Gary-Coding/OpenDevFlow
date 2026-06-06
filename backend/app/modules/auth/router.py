from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_password
from app.db.session import get_db
from app.models.user import Menu, User
from app.modules.auth.dependencies import CurrentUser, get_current_user

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def collect_role_names(user: User) -> list[str]:
    return sorted({role.name for role in user.roles})


def collect_permission_codes(user: User) -> list[str]:
    permissions = {
        menu.permission
        for role in user.roles
        for menu in role.menus
        if menu.permission and menu.status == "active"
    }
    if "admin" in collect_role_names(user):
        permissions.add("*:*:*")
    return sorted(permissions)


def serialize_menu(menu: Menu) -> dict:
    return {
        "id": str(menu.id),
        "parent_id": str(menu.parent_id) if menu.parent_id else None,
        "menu_name": menu.menu_name,
        "menu_type": menu.menu_type,
        "path": menu.path,
        "component": menu.component,
        "permission": menu.permission,
        "icon": menu.icon,
        "order_num": menu.order_num,
        "visible": menu.visible,
        "status": menu.status,
    }


def build_menu_tree(menus: list[Menu]) -> list[dict]:
    allowed = [
        serialize_menu(menu)
        for menu in menus
        if menu.status == "active" and menu.visible and menu.menu_type in {"M", "C"}
    ]
    by_id = {item["id"]: {**item, "children": []} for item in allowed}
    roots = []
    for item in by_id.values():
        parent_id = item["parent_id"]
        if parent_id and parent_id in by_id:
            by_id[parent_id]["children"].append(item)
        else:
            roots.append(item)

    def sort_items(items: list[dict]) -> list[dict]:
        items.sort(key=lambda x: (x["order_num"], x["menu_name"]))
        for child in items:
            sort_items(child["children"])
        return items

    return sort_items(roots)


def collect_user_menus(user: User, db: Session) -> list[dict]:
    if "admin" in collect_role_names(user):
        menus = db.scalars(select(Menu).where(Menu.status == "active")).all()
    else:
        seen = {}
        for role in user.roles:
            for menu in role.menus:
                seen[str(menu.id)] = menu
                parent_id = menu.parent_id
                while parent_id:
                    parent = db.get(Menu, parent_id)
                    if parent is None:
                        break
                    seen[str(parent.id)] = parent
                    parent_id = parent.parent_id
        menus = list(seen.values())
    return build_menu_tree(menus)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == payload.username))
    if (
        user is None
        or not user.is_active
        or not verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    roles = collect_role_names(user)
    permissions = collect_permission_codes(user)
    menus = collect_user_menus(user, db)
    user.last_login_at = func.now()
    db.commit()
    token = create_access_token(
        subject=str(user.id),
        roles=roles,
        permissions=permissions,
        menus=menus,
        username=user.username,
        display_name=user.display_name,
    )
    return TokenResponse(access_token=token)


@router.post("/refresh", response_model=TokenResponse)
def refresh(current_user: CurrentUser = Depends(get_current_user)):
    token = create_access_token(
        subject=current_user.id,
        roles=current_user.roles,
        permissions=current_user.permissions,
        menus=current_user.menus or [],
        username=current_user.username,
        display_name=current_user.display_name,
    )
    return TokenResponse(access_token=token)


@router.get("/me")
def me(current_user: CurrentUser = Depends(get_current_user)):
    return current_user
