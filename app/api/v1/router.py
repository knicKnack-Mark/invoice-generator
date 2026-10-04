from fastapi import APIRouter

from app.api.v1 import auth, clients, dashboard, expense_categories, expenses, health, invoices, organizations, payments, projects, receipts
from app.core.config import settings

api_router = APIRouter(prefix=settings.api_prefix)
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(organizations.router)
api_router.include_router(clients.router)
api_router.include_router(projects.router)
api_router.include_router(expense_categories.router)
api_router.include_router(expenses.router)
api_router.include_router(receipts.router)
api_router.include_router(invoices.router)
api_router.include_router(payments.router)
api_router.include_router(dashboard.router)

# Mounted separately (not under /api/v1) in app/main.py — see invoices.public_router.
public_router = invoices.public_router
