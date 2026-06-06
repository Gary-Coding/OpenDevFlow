from fastapi import APIRouter, Depends

from app.models.user import User
from app.modules.auth.dependencies import get_current_orm_user

router = APIRouter()


@router.get("/me")
def get_profile(current_user: User = Depends(get_current_orm_user)):
    return {
        "id": str(current_user.id),
        "username": current_user.username,
        "display_name": current_user.display_name,
        "email": current_user.email,
        "is_active": current_user.is_active,
        "roles": sorted(role.name for role in current_user.roles),
        "company_id": str(current_user.company_id) if current_user.company_id else None,
        "company_name": current_user.company.name if current_user.company else None,
        "department_id": str(current_user.department_id) if current_user.department_id else None,
        "department_name": current_user.department.name if current_user.department else None,
        "last_login_at": current_user.last_login_at.isoformat() if current_user.last_login_at else None,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
    }
