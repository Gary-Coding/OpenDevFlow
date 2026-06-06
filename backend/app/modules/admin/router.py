from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from app.core.rbac import require_permissions
from app.core.security import hash_password
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.organization import Company, Department, OrganizationMember
from app.models.user import Menu, Role, User
from app.modules.auth.dependencies import CurrentUser, get_current_orm_user, get_current_user

router = APIRouter()


class UserPayload(BaseModel):
    username: str = Field(min_length=2, max_length=80)
    display_name: str = Field(min_length=1, max_length=120)
    email: str | None = None
    password: str | None = Field(default=None, min_length=6, max_length=80)
    is_active: bool = True
    role_ids: list[UUID] = []
    company_id: UUID | None = None
    department_id: UUID | None = None
    dev_group_ids: list[UUID] = []


class UserUpdatePayload(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    email: str | None = None
    is_active: bool = True
    role_ids: list[UUID] = []
    company_id: UUID | None = None
    department_id: UUID | None = None
    dev_group_ids: list[UUID] = []


class PasswordPayload(BaseModel):
    password: str = Field(min_length=6, max_length=80)


class RolePayload(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    description: str | None = None
    menu_ids: list[UUID] = []
    data_scope: str = Field(default="self", max_length=20)
    company_id: UUID | None = None
    custom_department_ids: list[UUID] = []


class MenuPayload(BaseModel):
    parent_id: UUID | None = None
    menu_name: str = Field(min_length=1, max_length=120)
    menu_type: str = Field(min_length=1, max_length=1)
    path: str | None = None
    component: str | None = None
    permission: str | None = None
    icon: str | None = None
    order_num: int = 0
    visible: bool = True
    status: str = Field(default="active", max_length=20)


class CompanyPayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    code: str = Field(min_length=1, max_length=80)
    status: str = Field(default="active", max_length=20)


VALID_DATA_SCOPES = {"all", "custom_dept", "dept", "dept_and_child", "self"}
VALID_MENU_TYPES = {"M", "C", "F"}


AUDIT_ACTION_LABELS = {
    # 用户与角色基础
    "system.user.create": "新增用户",
    "system.user.update": "修改用户",
    "system.user.delete": "删除用户",
    "system.user.reset_password": "重置密码",
    "system.role.create": "新增角色",
    "system.role.update": "修改角色",
    "system.role.delete": "删除角色",
    "system.role.grant": "角色授权",
    "system.role.data_scope_update": "修改角色数据范围",
    "system.menu.create": "新增菜单",
    "system.menu.update": "修改菜单",
    "system.menu.delete": "删除菜单",
    "system.company.create": "新增公司",
    "system.company.update": "修改公司",
    "system.company.delete": "删除公司",
    # 部门
    "system.department.create": "新增部门",
    "system.department.update": "修改部门",
    "system.department.delete": "删除部门",
    # 需求
    "demand.create": "创建需求",
    "demand.update": "修改需求",
    "demand.delete": "删除需求",
    "demand.archive": "归档需求",
    "demand.members.import_org": "导入组织架构成员",
    # 兼容旧 action 命名
    "create_demand": "创建需求",
    "update_demand": "修改需求",
    "delete_demand": "删除需求",
    "archive_demand": "归档需求",
    # 工作流
    "workflow.create": "新建工作流",
    "workflow.stage.advance": "推进工作流阶段",
    "workflow.stage.block": "阻塞工作流阶段",
    "workflow.stage.resume": "恢复工作流阶段",
    "advance_workflow_stage": "推进工作流阶段",
    "block_workflow_stage": "阻塞工作流阶段",
    "resume_workflow_stage": "恢复工作流阶段",
}


def _role_names(user: User) -> list[str]:
    return sorted(role.name for role in user.roles)


def is_super_admin(user: User) -> bool:
    return "admin" in _role_names(user)


def _permission_codes(role: Role) -> list[str]:
    return sorted({menu.permission for menu in role.menus if menu.permission})


def serialize_user(user: User) -> dict:
    dev_group_members = [
        member for member in user.organization_members
        if member.department and member.department.org_type == "dev_group"
    ]
    return {
        "id": str(user.id),
        "username": user.username,
        "display_name": user.display_name,
        "email": user.email,
        "is_active": user.is_active,
        "roles": _role_names(user),
        "role_ids": [str(role.id) for role in user.roles],
        "company_id": str(user.company_id) if user.company_id else None,
        "company_name": user.company.name if user.company else None,
        "department_id": str(user.department_id) if user.department_id else None,
        "department_name": user.department.name if user.department else None,
        "dev_group_ids": [str(member.department_id) for member in dev_group_members],
        "dev_group_names": [member.department.name for member in dev_group_members],
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def serialize_role(role: Role) -> dict:
    return {
        "id": str(role.id),
        "name": role.name,
        "description": role.description,
        "menu_ids": [str(menu.id) for menu in role.menus],
        "permissions": _permission_codes(role),
        "data_scope": role.data_scope,
        "custom_department_ids": [str(d.id) for d in role.custom_departments],
        "custom_department_names": [d.name for d in role.custom_departments],
        "created_at": role.created_at.isoformat() if role.created_at else None,
    }


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
        "created_at": menu.created_at.isoformat() if menu.created_at else None,
    }


def serialize_company(company: Company) -> dict:
    return {
        "id": str(company.id),
        "name": company.name,
        "code": company.code,
        "status": company.status,
        "created_at": company.created_at.isoformat() if company.created_at else None,
        "updated_at": company.updated_at.isoformat() if company.updated_at else None,
    }


def serialize_audit_log(log: AuditLog, actor: User | None = None) -> dict:
    return {
        "id": str(log.id),
        "actor_user_id": str(log.actor_user_id) if log.actor_user_id else None,
        "actor_username": actor.username if actor else None,
        "actor_display_name": actor.display_name if actor else None,
        "action": log.action,
        "action_label": AUDIT_ACTION_LABELS.get(log.action, log.action),
        "target_type": log.target_type,
        "target_id": str(log.target_id) if log.target_id else None,
        "metadata": log.metadata_ or {},
        "created_at": log.created_at.isoformat() if log.created_at else None,
    }


def write_audit_log(
    db: Session,
    current_user: CurrentUser,
    action: str,
    target_type: str,
    target_id: UUID | None,
    metadata: dict,
) -> None:
    db.add(
        AuditLog(
            actor_user_id=UUID(current_user.id),
            action=action,
            target_type=target_type,
            target_id=target_id,
            metadata_=metadata,
        )
    )


def write_audit_log_orm(
    db: Session,
    current_user: User,
    action: str,
    target_type: str,
    target_id: UUID | None,
    metadata: dict,
) -> None:
    """ORM User 版本的审计日志写入"""
    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            metadata_=metadata,
        )
    )


def get_user_or_404(user_id: UUID, db: Session) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return user


def get_role_or_404(role_id: UUID, db: Session) -> Role:
    role = db.get(Role, role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色不存在")
    return role


def get_menu_or_404(menu_id: UUID, db: Session) -> Menu:
    menu = db.get(Menu, menu_id)
    if menu is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="菜单不存在")
    return menu


def load_roles(db: Session, role_ids: list[UUID]) -> list[Role]:
    if not role_ids:
        return []
    roles = db.scalars(select(Role).where(Role.id.in_(role_ids))).all()
    if len(roles) != len(set(role_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="选择的角色不存在")
    return roles


def has_admin_role(roles: list[Role]) -> bool:
    return any(role.name == "admin" for role in roles)


def load_menus(db: Session, menu_ids: list[UUID]) -> list[Menu]:
    if not menu_ids:
        return []
    menus = db.scalars(select(Menu).where(Menu.id.in_(menu_ids))).all()
    if len(menus) != len(set(menu_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="选择的菜单不存在")
    return menus


def load_departments(db: Session, department_ids: list[UUID], company_id: UUID | None) -> list[Department]:
    """加载部门列表，校验都在指定公司下"""
    if not department_ids:
        return []
    departments = db.scalars(select(Department).where(Department.id.in_(department_ids))).all()
    if len(departments) != len(set(department_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="选择的组织架构不存在")
    if company_id is not None:
        for d in departments:
            if d.company_id != company_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="组织架构不属于当前公司")
    return departments


def load_dev_groups(db: Session, dev_group_ids: list[UUID], company_id: UUID | None) -> list[Department]:
    dev_groups = load_departments(db, dev_group_ids, company_id)
    invalid = [item for item in dev_groups if item.org_type != "dev_group"]
    if invalid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="参与开发组只能选择开发组")
    return dev_groups


def sync_user_dev_groups(db: Session, user: User, dev_groups: list[Department]) -> None:
    target_ids = {item.id for item in dev_groups}
    current_members = db.scalars(
        select(OrganizationMember)
        .join(Department, Department.id == OrganizationMember.department_id)
        .where(
            OrganizationMember.user_id == user.id,
            Department.org_type == "dev_group",
        )
    ).all()
    current_by_dept_id = {member.department_id: member for member in current_members}

    for dept_id, member in current_by_dept_id.items():
        if dept_id not in target_ids:
            db.delete(member)

    for dept in dev_groups:
        if dept.id not in current_by_dept_id:
            db.add(
                OrganizationMember(
                    department_id=dept.id,
                    user_id=user.id,
                    member_role="member",
                )
            )


def resolve_company_id(
    db: Session,
    current_user: User,
    requested_company_id: UUID | None,
    required: bool = False,
) -> UUID | None:
    """普通管理员固定为本人公司；超级管理员可指定目标公司。"""
    if is_super_admin(current_user):
        target_company_id = requested_company_id or current_user.company_id
    else:
        if requested_company_id and requested_company_id != current_user.company_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权维护其他公司数据")
        target_company_id = current_user.company_id
    if target_company_id is None:
        if required:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择公司")
        return None
    if db.get(Company, target_company_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="公司不存在")
    return target_company_id


def resolve_department_id(
    db: Session,
    payload_department_id: UUID | None,
    current_user: User,
    target_company_id: UUID | None,
) -> UUID | None:
    """解析用户的 department_id：前端传值则校验，否则默认管理员的"""
    target_id = payload_department_id
    if target_id is None and not is_super_admin(current_user) and target_company_id == current_user.company_id:
        target_id = current_user.department_id
    if target_id is None:
        return None
    dept = db.get(Department, target_id)
    if dept is None or (target_company_id is not None and dept.company_id != target_company_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前公司下未找到该组织架构")
    if dept.org_type != "department":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户主归属只能选择部门，项目组成员请在组织架构成员中维护")
    return target_id


def ensure_unique_user(db: Session, username: str, email: str | None, exclude_id: UUID | None = None) -> None:
    filters = [User.username == username]
    if email:
        filters.append(User.email == email)
    query = select(User).where(or_(*filters))
    if exclude_id:
        query = query.where(User.id != exclude_id)
    if db.scalar(query):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名或邮箱已存在")


def ensure_unique_role(db: Session, name: str, exclude_id: UUID | None = None) -> None:
    query = select(Role).where(Role.name == name)
    if exclude_id:
        query = query.where(Role.id != exclude_id)
    if db.scalar(query):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="角色标识已存在")


def ensure_unique_company_code(db: Session, code: str, exclude_id: UUID | None = None) -> None:
    query = select(Company).where(Company.code == code)
    if exclude_id:
        query = query.where(Company.id != exclude_id)
    if db.scalar(query):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="公司编码已存在")


def get_company_or_404(company_id: UUID, db: Session) -> Company:
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="公司不存在")
    return company


def validate_menu_payload(db: Session, payload: MenuPayload, menu_id: UUID | None = None) -> None:
    if payload.menu_type not in VALID_MENU_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="菜单类型无效")
    if payload.parent_id is None:
        return
    if menu_id and payload.parent_id == menu_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能将上级设置为自身")
    parent = db.get(Menu, payload.parent_id)
    if parent is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="上级菜单不存在")
    if parent.menu_type == "F":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="按钮权限不能作为上级菜单")

    current_parent_id = parent.parent_id
    while menu_id and current_parent_id:
        if current_parent_id == menu_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能将子菜单设置为上级菜单")
        ancestor = db.get(Menu, current_parent_id)
        current_parent_id = ancestor.parent_id if ancestor else None


@router.get("/companies", dependencies=[Depends(require_permissions("system:company:list"))])
def list_companies(
    q: str | None = Query(default=None),
    status_: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
):
    query = select(Company)
    count_query = select(func.count()).select_from(Company)
    if q:
        keyword = f"%{q.strip()}%"
        condition = or_(Company.name.ilike(keyword), Company.code.ilike(keyword))
        query = query.where(condition)
        count_query = count_query.where(condition)
    if status_:
        query = query.where(Company.status == status_)
        count_query = count_query.where(Company.status == status_)
    total = db.scalar(count_query) or 0
    companies = db.scalars(query.order_by(Company.created_at.asc())).all()
    return {"items": [serialize_company(company) for company in companies], "total": total}


@router.get("/company", dependencies=[Depends(require_permissions("system:company:list"))])
def get_current_company(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    company = db.get(Company, current_user.company_id) if current_user.company_id else None
    if company is None:
        company = db.scalar(select(Company).order_by(Company.created_at.asc()))
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="公司不存在")
    return serialize_company(company)


@router.post("/companies", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permissions("system:company:create"))])
def create_company(
    payload: CompanyPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    code = payload.code.strip()
    ensure_unique_company_code(db, code)
    company = Company(name=payload.name.strip(), code=code, status=payload.status)
    db.add(company)
    db.flush()
    write_audit_log_orm(
        db,
        current_user,
        "system.company.create",
        "company",
        company.id,
        serialize_company(company),
    )
    db.commit()
    db.refresh(company)
    return serialize_company(company)


@router.put("/companies/{company_id}", dependencies=[Depends(require_permissions("system:company:update"))])
def update_company(
    company_id: UUID,
    payload: CompanyPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    company = get_company_or_404(company_id, db)
    code = payload.code.strip()
    ensure_unique_company_code(db, code, exclude_id=company.id)
    before = serialize_company(company)
    company.name = payload.name.strip()
    company.code = code
    company.status = payload.status
    db.flush()
    write_audit_log_orm(
        db,
        current_user,
        "system.company.update",
        "company",
        company.id,
        {"before": before, "after": serialize_company(company)},
    )
    db.commit()
    db.refresh(company)
    return serialize_company(company)


@router.delete("/companies/{company_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_permissions("system:company:delete"))])
def delete_company(
    company_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    company = get_company_or_404(company_id, db)
    dept_count = db.scalar(select(func.count()).select_from(Department).where(Department.company_id == company.id)) or 0
    user_count = db.scalar(select(func.count()).select_from(User).where(User.company_id == company.id)) or 0
    if dept_count > 0 or user_count > 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="公司下存在组织架构或用户，不能删除")
    write_audit_log_orm(
        db,
        current_user,
        "system.company.delete",
        "company",
        company.id,
        serialize_company(company),
    )
    db.delete(company)
    db.commit()


@router.get("/users", dependencies=[Depends(require_permissions("system:user:list"))])
def list_users(
    q: str | None = Query(default=None),
    company_id: UUID | None = Query(default=None),
    department_id: UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    target_company_id = resolve_company_id(db, current_user, company_id)
    query = select(User)
    count_query = select(func.count()).select_from(User)
    if target_company_id is not None:
        query = query.where(User.company_id == target_company_id)
        count_query = count_query.where(User.company_id == target_company_id)
    if q:
        keyword = f"%{q.strip()}%"
        condition = or_(User.username.ilike(keyword), User.display_name.ilike(keyword), User.email.ilike(keyword))
        query = query.where(condition)
        count_query = count_query.where(condition)
    if department_id:
        department = db.get(Department, department_id)
        if department is None or (target_company_id is not None and department.company_id != target_company_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="组织架构不存在")
        if department.org_type != "department":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户列表只能按部门筛选")
        dept_id = str(department_id)
        child_dept_ids = db.scalars(
            select(Department.id).where(
                or_(
                    Department.id == department_id,
                    Department.ancestors == dept_id,
                    Department.ancestors.like(f"{dept_id},%"),
                    Department.ancestors.like(f"%,{dept_id},%"),
                    Department.ancestors.like(f"%,{dept_id}"),
                )
            )
        ).all()
        query = query.where(User.department_id.in_(child_dept_ids))
        count_query = count_query.where(User.department_id.in_(child_dept_ids))
    total = db.scalar(count_query) or 0
    users = db.scalars(
        query.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {"items": [serialize_user(user) for user in users], "total": total}


@router.post("/users", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permissions("system:user:create"))])
def create_user(
    payload: UserPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    username = payload.username.strip()
    email = payload.email.strip() if payload.email else None
    ensure_unique_user(db, username, email)
    if not payload.password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请输入初始密码")

    roles = load_roles(db, payload.role_ids)
    if has_admin_role(roles):
        target_company_id = None
        department_id = None
        dev_groups = []
    else:
        target_company_id = resolve_company_id(db, current_user, payload.company_id, required=True)
        department_id = resolve_department_id(db, payload.department_id, current_user, target_company_id)
        if department_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择所属部门")
        dev_groups = load_dev_groups(db, payload.dev_group_ids, target_company_id)
    user = User(
        username=username,
        display_name=payload.display_name.strip(),
        email=email,
        password_hash=hash_password(payload.password),
        is_active=payload.is_active,
        company_id=target_company_id,
        department_id=department_id,
    )
    user.roles = roles
    db.add(user)
    db.flush()
    sync_user_dev_groups(db, user, dev_groups)
    db.flush()
    db.refresh(user)
    write_audit_log_orm(
        db,
        current_user,
        "system.user.create",
        "user",
        user.id,
        {
            "username": user.username,
            "display_name": user.display_name,
            "email": user.email,
            "is_active": user.is_active,
            "roles": _role_names(user),
            "company_id": str(user.company_id) if user.company_id else None,
            "company_name": user.company.name if user.company else None,
            "department_id": str(user.department_id) if user.department_id else None,
            "department_name": user.department.name if user.department else None,
            "dev_group_ids": [str(item.id) for item in dev_groups],
            "dev_group_names": [item.name for item in dev_groups],
        },
    )
    db.commit()
    db.refresh(user)
    return serialize_user(user)


@router.put("/users/{user_id}", dependencies=[Depends(require_permissions("system:user:update"))])
def update_user(
    user_id: UUID,
    payload: UserUpdatePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    user = get_user_or_404(user_id, db)
    if not is_super_admin(current_user) and user.company_id != current_user.company_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权维护其他公司数据")
    before = {
        "display_name": user.display_name,
        "email": user.email,
        "is_active": user.is_active,
        "roles": _role_names(user),
        "company_id": str(user.company_id) if user.company_id else None,
        "company_name": user.company.name if user.company else None,
        "department_id": str(user.department_id) if user.department_id else None,
        "department_name": user.department.name if user.department else None,
        "dev_group_ids": [str(member.department_id) for member in user.organization_members if member.department and member.department.org_type == "dev_group"],
        "dev_group_names": [member.department.name for member in user.organization_members if member.department and member.department.org_type == "dev_group"],
    }
    email = payload.email.strip() if payload.email else None
    ensure_unique_user(db, user.username, email, exclude_id=user.id)
    roles = load_roles(db, payload.role_ids)
    if has_admin_role(roles):
        target_company_id = None
        department_id = None
        dev_groups = []
    else:
        target_company_id = resolve_company_id(db, current_user, payload.company_id or user.company_id, required=True)
        department_id = resolve_department_id(db, payload.department_id, current_user, target_company_id)
        if department_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择所属部门")
        dev_groups = load_dev_groups(db, payload.dev_group_ids, target_company_id)
    user.display_name = payload.display_name.strip()
    user.email = email
    user.is_active = payload.is_active
    user.roles = roles
    user.company_id = target_company_id
    user.department_id = department_id
    db.flush()
    sync_user_dev_groups(db, user, dev_groups)
    db.flush()
    db.refresh(user)
    write_audit_log_orm(
        db,
        current_user,
        "system.user.update",
        "user",
        user.id,
        {
            "username": user.username,
            "before": before,
            "after": {
                "display_name": user.display_name,
                "email": user.email,
                "is_active": user.is_active,
                "roles": _role_names(user),
                "company_id": str(user.company_id) if user.company_id else None,
                "company_name": user.company.name if user.company else None,
                "department_id": str(user.department_id) if user.department_id else None,
                "department_name": user.department.name if user.department else None,
                "dev_group_ids": [str(item.id) for item in dev_groups],
                "dev_group_names": [item.name for item in dev_groups],
            },
        },
    )
    db.commit()
    db.refresh(user)
    return serialize_user(user)


@router.post("/users/{user_id}/reset-password", dependencies=[Depends(require_permissions("system:user:reset-password"))])
def reset_password(
    user_id: UUID,
    payload: PasswordPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    user = get_user_or_404(user_id, db)
    if not is_super_admin(current_user) and user.company_id != current_user.company_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权维护其他公司数据")
    user.password_hash = hash_password(payload.password)
    write_audit_log_orm(
        db,
        current_user,
        "system.user.reset_password",
        "user",
        user.id,
        {"username": user.username, "display_name": user.display_name},
    )
    db.commit()
    return {"ok": True}


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_permissions("system:user:delete"))])
def delete_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能删除当前登录用户")
    user = get_user_or_404(user_id, db)
    if not is_super_admin(current_user) and user.company_id != current_user.company_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权维护其他公司数据")
    write_audit_log_orm(
        db,
        current_user,
        "system.user.delete",
        "user",
        user.id,
        {
            "username": user.username,
            "display_name": user.display_name,
            "email": user.email,
            "roles": _role_names(user),
        },
    )
    db.delete(user)
    db.commit()


@router.get("/roles", dependencies=[Depends(require_permissions("system:role:list"))])
def list_roles(db: Session = Depends(get_db)):
    roles = db.scalars(select(Role).order_by(Role.name.asc())).all()
    return {"items": [serialize_role(role) for role in roles], "total": len(roles)}


@router.post("/roles", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permissions("system:role:create"))])
def create_role(
    payload: RolePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    if payload.data_scope not in VALID_DATA_SCOPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="数据范围无效")
    name = payload.name.strip()
    ensure_unique_role(db, name)
    role = Role(
        name=name,
        description=payload.description.strip() if payload.description else None,
        data_scope=payload.data_scope,
    )
    role.menus = load_menus(db, payload.menu_ids)
    # 仅当 data_scope=custom_dept 时保存自定义部门，否则强制清空
    if payload.data_scope == "custom_dept":
        target_company_id = resolve_company_id(db, current_user, payload.company_id, required=True)
        role.custom_departments = load_departments(db, payload.custom_department_ids, target_company_id)
    else:
        role.custom_departments = []
    db.add(role)
    db.flush()
    db.refresh(role)
    write_audit_log_orm(
        db,
        current_user,
        "system.role.create",
        "role",
        role.id,
        {
            "name": role.name,
            "description": role.description,
            "permissions": _permission_codes(role),
            "menu_ids": [str(menu.id) for menu in role.menus],
            "data_scope": role.data_scope,
            "custom_department_ids": [str(d.id) for d in role.custom_departments],
        },
    )
    db.commit()
    db.refresh(role)
    return serialize_role(role)


@router.put("/roles/{role_id}", dependencies=[Depends(require_permissions("system:role:update"))])
def update_role(
    role_id: UUID,
    payload: RolePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    if payload.data_scope not in VALID_DATA_SCOPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="数据范围无效")
    role = get_role_or_404(role_id, db)
    before = {
        "name": role.name,
        "description": role.description,
        "permissions": _permission_codes(role),
        "menu_ids": [str(menu.id) for menu in role.menus],
        "data_scope": role.data_scope,
        "custom_department_ids": [str(d.id) for d in role.custom_departments],
    }
    if role.name == "admin" and payload.name.strip() != "admin":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能重命名内置管理员角色")
    name = payload.name.strip()
    ensure_unique_role(db, name, exclude_id=role.id)
    role.name = name
    role.description = payload.description.strip() if payload.description else None
    role.menus = load_menus(db, payload.menu_ids)
    role.data_scope = payload.data_scope
    # 仅当 data_scope=custom_dept 时保存自定义部门，否则强制清空
    if payload.data_scope == "custom_dept":
        target_company_id = resolve_company_id(db, current_user, payload.company_id, required=True)
        role.custom_departments = load_departments(db, payload.custom_department_ids, target_company_id)
    else:
        role.custom_departments = []
    db.flush()
    db.refresh(role)
    after = {
        "name": role.name,
        "description": role.description,
        "permissions": _permission_codes(role),
        "menu_ids": [str(menu.id) for menu in role.menus],
        "data_scope": role.data_scope,
        "custom_department_ids": [str(d.id) for d in role.custom_departments],
    }
    # 数据范围变化时使用专用 action，便于按主题筛选
    action = "system.role.data_scope_update" if (
        before["data_scope"] != after["data_scope"]
        or before["custom_department_ids"] != after["custom_department_ids"]
    ) else "system.role.update"
    write_audit_log_orm(
        db,
        current_user,
        action,
        "role",
        role.id,
        {"before": before, "after": after},
    )
    db.commit()
    db.refresh(role)
    return serialize_role(role)


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_permissions("system:role:delete"))])
def delete_role(
    role_id: UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    role = get_role_or_404(role_id, db)
    if role.name in {"admin", "user"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能删除内置角色")
    if role.users:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="角色已分配给用户，不能删除")
    write_audit_log(
        db,
        current_user,
        "system.role.delete",
        "role",
        role.id,
        {
            "name": role.name,
            "description": role.description,
            "permissions": _permission_codes(role),
        },
    )
    db.delete(role)
    db.commit()


@router.get("/menus", dependencies=[Depends(require_permissions("system:menu:list"))])
def list_menus(db: Session = Depends(get_db)):
    menus = db.scalars(
        select(Menu).order_by(Menu.order_num.asc(), Menu.created_at.asc())
    ).all()
    return {"items": [serialize_menu(menu) for menu in menus], "total": len(menus)}


@router.post("/menus", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permissions("system:menu:create"))])
def create_menu(
    payload: MenuPayload,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    validate_menu_payload(db, payload)
    menu = Menu(
        parent_id=payload.parent_id,
        menu_name=payload.menu_name.strip(),
        menu_type=payload.menu_type,
        path=payload.path.strip() if payload.path else None,
        component=payload.component.strip() if payload.component else None,
        permission=payload.permission.strip() if payload.permission else None,
        icon=payload.icon.strip() if payload.icon else None,
        order_num=payload.order_num,
        visible=payload.visible,
        status=payload.status,
    )
    db.add(menu)
    db.flush()
    write_audit_log(
        db,
        current_user,
        "system.menu.create",
        "menu",
        menu.id,
        {
            "menu_name": menu.menu_name,
            "menu_type": menu.menu_type,
            "parent_id": str(menu.parent_id) if menu.parent_id else None,
            "permission": menu.permission,
        },
    )
    db.commit()
    db.refresh(menu)
    return serialize_menu(menu)


@router.patch("/menus/{menu_id}", dependencies=[Depends(require_permissions("system:menu:update"))])
def update_menu(
    menu_id: UUID,
    payload: MenuPayload,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    validate_menu_payload(db, payload, menu_id=menu_id)
    menu = get_menu_or_404(menu_id, db)
    before = serialize_menu(menu)
    menu.parent_id = payload.parent_id
    menu.menu_name = payload.menu_name.strip()
    menu.menu_type = payload.menu_type
    menu.path = payload.path.strip() if payload.path else None
    menu.component = payload.component.strip() if payload.component else None
    menu.permission = payload.permission.strip() if payload.permission else None
    menu.icon = payload.icon.strip() if payload.icon else None
    menu.order_num = payload.order_num
    menu.visible = payload.visible
    menu.status = payload.status
    db.flush()
    write_audit_log(
        db,
        current_user,
        "system.menu.update",
        "menu",
        menu.id,
        {"before": before, "after": serialize_menu(menu)},
    )
    db.commit()
    db.refresh(menu)
    return serialize_menu(menu)


@router.delete("/menus/{menu_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_permissions("system:menu:delete"))])
def delete_menu(
    menu_id: UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    menu = get_menu_or_404(menu_id, db)
    child_count = db.scalar(select(func.count()).select_from(Menu).where(Menu.parent_id == menu_id))
    if child_count and child_count > 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="菜单下存在子菜单或按钮，不能删除")
    write_audit_log(
        db,
        current_user,
        "system.menu.delete",
        "menu",
        menu.id,
        serialize_menu(menu),
    )
    db.delete(menu)
    db.commit()


@router.get("/audit-logs", dependencies=[Depends(require_permissions("system:audit:list"))])
def list_audit_logs(
    q: str | None = Query(default=None),
    action: str | None = Query(default=None),
    target_type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = select(AuditLog, User).join(User, AuditLog.actor_user_id == User.id, isouter=True)
    count_query = select(func.count()).select_from(AuditLog).join(User, AuditLog.actor_user_id == User.id, isouter=True)
    conditions = []
    if action:
        conditions.append(AuditLog.action == action)
    if target_type:
        conditions.append(AuditLog.target_type == target_type)
    if q:
        keyword = f"%{q.strip()}%"
        conditions.append(
            or_(
                AuditLog.action.ilike(keyword),
                AuditLog.target_type.ilike(keyword),
                User.username.ilike(keyword),
                User.display_name.ilike(keyword),
                cast(AuditLog.metadata_, String).ilike(keyword),
            )
        )
    for condition in conditions:
        query = query.where(condition)
        count_query = count_query.where(condition)
    total = db.scalar(count_query) or 0
    rows = db.execute(
        query.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [serialize_audit_log(log, actor) for log, actor in rows],
        "total": total,
        "actions": [{"value": key, "label": value} for key, value in AUDIT_ACTION_LABELS.items()],
    }
