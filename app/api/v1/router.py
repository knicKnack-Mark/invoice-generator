from fastapi import APIRouter

from app.api.v1 import auth, clients, expense_categories, expenses, health, organizations, projects
from app.core.config import settings

api_router = APIRouter(prefix=settings.api_prefix)
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(organizations.router)
api_router.include_router(clients.router)
api_router.include_router(projects.router)
api_router.include_router(expense_categories.router)
api_router.include_router(expenses.router)