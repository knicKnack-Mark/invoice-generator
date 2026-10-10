from fastapi import APIRouter

from app.api.v1 import (
    auth,
    clients,
    dashboard,
    expense_categories,
    expenses,
    health,
    invoices,
    notifications,
    organizations,
    payments,
    projects,
    receipts,
    recurring_invoices,
    reports,
    settings as settings_routes,  # aliased so it doesn't shadow app.core.config.settings
    time_entries,
)
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
api_router.include_router(time_entries.router)
api_router.include_router(recurring_invoices.router)
api_router.include_router(notifications.router)
api_router.include_router(settings_routes.router)
api_router.include_router(reports.router)

# Mounted separately (not under /api/v1) in app/main.py. See invoices.public_router.
public_router = invoices.public_router