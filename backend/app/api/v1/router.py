from fastapi import APIRouter

from app.modules.admin.router import router as admin_router
from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as users_router
from app.modules.demands.router import router as demands_router
from app.modules.departments.router import router as departments_router
from app.modules.delivery.router import router as delivery_router
from app.modules.workflows.router import router as workflows_router
from app.modules.skills.router import router as skills_router
from app.modules.workspaces.router import router as workspaces_router
from app.modules.model_providers.router import router as model_providers_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(users_router, prefix="/users", tags=["users"])
api_router.include_router(admin_router, prefix="/admin", tags=["admin"])
api_router.include_router(departments_router, prefix="/departments", tags=["departments"])
api_router.include_router(workflows_router, prefix="/demands", tags=["workflows"])
api_router.include_router(demands_router, prefix="/demands", tags=["demands"])
api_router.include_router(delivery_router, prefix="/demands", tags=["delivery"])
api_router.include_router(skills_router, prefix="/skills", tags=["skills"])
api_router.include_router(workspaces_router, prefix="/demands", tags=["workspaces"])
api_router.include_router(model_providers_router, prefix="/model-providers", tags=["model-providers"])
