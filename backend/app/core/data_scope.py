"""数据范围权限过滤核心功能"""
from uuid import UUID
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.organization import Department, OrganizationMember
from app.models.demand import Demand, DemandMember


def get_user_widest_data_scope(user: User) -> str:
    """
    获取用户所有角色中最宽的数据范围

    优先级: all > dept_and_child > dept > custom_dept > self
    """
    if not user.roles:
        return "self"

    scope_priority = {
        "all": 5,
        "dept_and_child": 4,
        "dept": 3,
        "custom_dept": 2,
        "self": 1,
    }

    widest_scope = "self"
    max_priority = 0

    for role in user.roles:
        priority = scope_priority.get(role.data_scope, 0)
        if priority > max_priority:
            max_priority = priority
            widest_scope = role.data_scope

    return widest_scope


def get_department_and_children_ids(db: Session, department_id: UUID) -> list[UUID]:
    """
    获取指定部门及其所有下级部门的 ID 列表

    使用精确 LIKE 匹配避免误匹配（如 123 被误匹配到 1234）：
    - ancestors 等于 '{id}'（一级子部门）
    - ancestors 以 '{id},' 开头（多级子部门）
    - ancestors 包含 ',{id},'（中间层）
    - ancestors 以 ',{id}' 结尾（末层）
    """
    result = [department_id]

    dept_id_str = str(department_id)
    stmt = select(Department).where(
        or_(
            Department.ancestors == dept_id_str,
            Department.ancestors.like(f"{dept_id_str},%"),
            Department.ancestors.like(f"%,{dept_id_str},%"),
            Department.ancestors.like(f"%,{dept_id_str}"),
        )
    )
    children = db.execute(stmt).scalars().all()

    for child in children:
        result.append(child.id)

    return result


def get_custom_department_ids(user: User) -> list[UUID]:
    """
    获取用户所有角色的自定义部门 ID 列表（去重）

    只返回 data_scope='custom_dept' 的角色绑定的部门
    """
    dept_ids = set()

    for role in user.roles:
        if role.data_scope == "custom_dept" and role.custom_departments:
            for dept in role.custom_departments:
                dept_ids.add(dept.id)

    return list(dept_ids)


def _apply_company_filter(query, current_user: User):
    """所有数据范围都强制限定当前公司边界（多租户隔离底线）"""
    if current_user.company_id is not None:
        query = query.where(Demand.company_id == current_user.company_id)
    return query


def apply_demand_data_scope(query, current_user: User, db: Session):
    """
    对需求查询应用数据权限过滤

    所有分支都先加 company_id 过滤，保证多租户隔离

    Args:
        query: SQLAlchemy 查询对象，已经 select(Demand) 或 join 了其他表
        current_user: 当前用户对象（ORM User）
        db: 数据库 Session

    Returns:
        应用数据权限过滤后的查询对象
    """
    # 公司边界限制（所有分支都必须）
    query = _apply_company_filter(query, current_user)
    member_demand_ids = select(DemandMember.demand_id).where(DemandMember.user_id == current_user.id)
    org_member_department_ids = select(OrganizationMember.department_id).where(OrganizationMember.user_id == current_user.id)

    data_scope = get_user_widest_data_scope(current_user)

    if data_scope == "all":
        # 当前公司全部需求
        return query

    elif data_scope == "dept_and_child":
        # 当前公司 + 当前部门及下级部门
        if not current_user.department_id:
            query = query.where(or_(
                Demand.created_by == current_user.id,
                Demand.id.in_(member_demand_ids),
                Demand.department_id.in_(org_member_department_ids),
            ))
        else:
            dept_ids = get_department_and_children_ids(db, current_user.department_id)
            query = query.where(or_(
                Demand.department_id.in_(dept_ids),
                Demand.id.in_(member_demand_ids),
                Demand.department_id.in_(org_member_department_ids),
            ))
        return query

    elif data_scope == "dept":
        # 当前公司 + 当前部门
        if not current_user.department_id:
            query = query.where(or_(
                Demand.created_by == current_user.id,
                Demand.id.in_(member_demand_ids),
                Demand.department_id.in_(org_member_department_ids),
            ))
        else:
            query = query.where(or_(
                Demand.department_id == current_user.department_id,
                Demand.id.in_(member_demand_ids),
                Demand.department_id.in_(org_member_department_ids),
            ))
        return query

    elif data_scope == "custom_dept":
        # 当前公司 + 自定义部门
        dept_ids = get_custom_department_ids(current_user)
        if not dept_ids:
            query = query.where(or_(Demand.created_by == current_user.id, Demand.id.in_(member_demand_ids)))
        else:
            query = query.where(or_(Demand.department_id.in_(dept_ids), Demand.id.in_(member_demand_ids)))
        return query

    else:  # self
        # 当前公司 + 当前用户创建或参与
        query = query.where(or_(
            Demand.created_by == current_user.id,
            Demand.id.in_(member_demand_ids),
            Demand.department_id.in_(org_member_department_ids),
        ))
        return query


def check_demand_data_permission(demand: Demand, current_user: User, db: Session) -> bool:
    """
    检查用户是否有权限访问指定需求

    用于需求详情和关联资源（artifact, agent_run, review）的权限校验
    所有数据范围都先校验公司边界

    Returns:
        True: 有权限访问
        False: 无权限访问
    """
    data_scope = get_user_widest_data_scope(current_user)

    # 系统级超级管理员不属于任何公司，使用 all 数据范围访问全部需求。
    if data_scope == "all" and current_user.company_id is None:
        return True

    # 公司边界校验（非系统级账号必须）
    if current_user.company_id is None or demand.company_id != current_user.company_id:
        return False

    is_member = db.scalar(
        select(DemandMember.id)
        .where(DemandMember.demand_id == demand.id, DemandMember.user_id == current_user.id)
        .limit(1)
    )
    if is_member:
        return True

    is_org_member = db.scalar(
        select(OrganizationMember.id)
        .where(OrganizationMember.department_id == demand.department_id, OrganizationMember.user_id == current_user.id)
        .limit(1)
    )
    if is_org_member:
        return True

    if data_scope == "all":
        return True

    elif data_scope == "dept_and_child":
        if not current_user.department_id:
            return demand.created_by == current_user.id
        dept_ids = get_department_and_children_ids(db, current_user.department_id)
        return demand.department_id in dept_ids

    elif data_scope == "dept":
        if not current_user.department_id:
            return demand.created_by == current_user.id
        return demand.department_id == current_user.department_id

    elif data_scope == "custom_dept":
        dept_ids = get_custom_department_ids(current_user)
        if not dept_ids:
            return demand.created_by == current_user.id
        return demand.department_id in dept_ids

    else:  # self
        return demand.created_by == current_user.id
