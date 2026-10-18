"""Two-tenant isolation tests.

Registers two separate accounts (A and B), fills A with data, then checks that
B can't read it, change it, reference it, or see it in lists/reports.
Needs a REAL, migrated database. Use a throwaway one (TEST_DATABASE_URL).
Unlike the older tests, these FAIL (not skip) when the database is unreachable,
because a silently skipped isolation test proves nothing.
"""
import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.main import app
from app.models.base import engine

TODAY = date.today().isoformat()
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"isotest" * 10
CLIENT_A = "IsoTest-Client-A"
VENDOR_A = "IsoTest-Vendor-A"


@pytest.fixture(autouse=True)
async def require_database():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.fail(f"Isolation tests need a reachable, migrated database (set TEST_DATABASE_URL): {exc}")
    yield
    # Each test runs in its own event loop; drop pooled connections so the next one starts clean.
    await engine.dispose()


class Tenant:
    """One registered account with its own cookie jar (so A's and B's sessions never mix)."""

    def __init__(self, label: str):
        self.label = label
        self.http = AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")
        self.org_id = ""
        self.ids: dict[str, str] = {}

    async def register(self):
        tag = uuid.uuid4().hex[:8]
        r = await self.http.post("/api/v1/auth/register", json={
            "email": f"isotest-{self.label.lower()}-{tag}@example.com",
            "password": "correct-horse-battery-staple",
            "full_name": f"IsoTest {self.label}",
            "organization_name": f"IsoTest Org {self.label} {tag}",
        })
        assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
        self.org_id = r.json()["organizations"][0]["id"]

    async def call(self, method: str, path: str, *, org_id: str | None = None, **kwargs):
        headers = {"X-Organization-Id": org_id or self.org_id}
        csrf = self.http.cookies.get("csrf_token")
        if csrf:
            headers["X-CSRF-Token"] = csrf
        return await self.http.request(method, f"/api/v1{path}", headers=headers, **kwargs)

    def all_ids(self) -> list[str]:
        return [*self.ids.values(), self.org_id]


def must(response, status: int):
    assert response.status_code == status, (
        f"SETUP FAILED: {response.request.method} {response.request.url} -> "
        f"{response.status_code} {response.text}"
    )
    return response.json()


async def seed_minimal(t: Tenant):
    data = must(await t.call("POST", "/clients", json={"name": f"IsoTest-Client-{t.label}", "currency": "USD"}), 201)
    t.ids["client"] = data["id"]


async def seed_full(t: Tenant):
    await seed_minimal(t)
    client_id = t.ids["client"]
    t.ids["project"] = must(await t.call("POST", "/projects", json={
        "name": "Proj", "client_id": client_id, "billing_type": "fixed", "fixed_rate": "100"}), 201)["id"]
    t.ids["category"] = must(await t.call("GET", "/expense-categories"), 200)[0]["id"]
    t.ids["expense"] = must(await t.call("POST", "/expenses", json={
        "client_id": client_id, "project_id": t.ids["project"], "category_id": t.ids["category"],
        "vendor": f"IsoTest-Vendor-{t.label}", "amount": "25.00", "currency": "USD",
        "expense_date": TODAY, "billable": True}), 201)["id"]
    t.ids["receipt"] = must(await t.call(
        "POST", f"/expenses/{t.ids['expense']}/receipts",
        files={"file": ("receipt.png", PNG_BYTES, "image/png")}), 201)["id"]
    t.ids["time_entry"] = must(await t.call("POST", "/time-entries", json={
        "client_id": client_id, "entry_date": TODAY, "duration_minutes": 60, "hourly_rate": "20"}), 201)["id"]
    t.ids["invoice"] = must(await t.call("POST", "/invoices", json={
        "client_id": client_id, "invoice_date": TODAY,
        "items": [{"description": "Work", "quantity": "1", "unit_price": "100"}]}), 201)["id"]
    must(await t.call("POST", f"/invoices/{t.ids['invoice']}/send"), 200)
    t.ids["payment"] = must(await t.call("POST", f"/invoices/{t.ids['invoice']}/payments", json={
        "amount": "10", "currency": "USD", "payment_date": TODAY, "payment_method": "Cash"}), 201)["id"]
    t.ids["recurring"] = must(await t.call("POST", "/recurring-invoices", json={
        "client_id": client_id, "frequency": "monthly", "start_date": TODAY,
        "items": [{"description": "Retainer", "unit_price": "50"}]}), 201)["id"]
    must(await t.call("PATCH", "/settings", json={"invoice_prefix": "AAA"}), 200)


@pytest.fixture
async def tenants():
    a, b = Tenant("A"), Tenant("B")
    await a.register()
    await b.register()
    await seed_full(a)
    await seed_minimal(b)  # B only has a client, so "B sees zero of A's data" is unambiguous
    yield a, b
    await a.http.aclose()
    await b.http.aclose()


def assert_nothing_of_a(response, a: Tenant):
    assert response.status_code == 200, f"{response.request.url} -> {response.status_code} {response.text}"
    body = response.text
    for value in [*a.all_ids(), CLIENT_A, VENDOR_A]:
        assert value not in body, f"LEAK: tenant A's {value!r} appeared in B's response to {response.request.url}"


# ---------------------------------------------------------------- reads

READ_ATTEMPTS = [
    "/clients/{client}", "/projects/{project}", "/expenses/{expense}",
    "/expenses/{expense}/receipts", "/receipts/{receipt}/file", "/time-entries/{time_entry}",
    "/invoices/{invoice}", "/invoices/{invoice}/pdf", "/payments/{payment}",
    "/recurring-invoices/{recurring}",
]


@pytest.mark.parametrize("template", READ_ATTEMPTS)
async def test_b_cannot_read_a_records_by_id(tenants, template):
    a, b = tenants
    path = template.format(**a.ids)
    r = await b.call("GET", path)
    assert r.status_code == 404, f"LEAK: B got {r.status_code} on GET {path}: {r.text[:200]}"


async def test_b_cannot_list_a_payments_for_invoice(tenants):
    a, b = tenants
    r = await b.call("GET", f"/invoices/{a.ids['invoice']}/payments")
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        assert_nothing_of_a(r, a)


LIST_PATHS = [
    "/clients", "/projects", "/expenses", "/invoices", "/payments", "/time-entries",
    "/recurring-invoices", "/expense-categories", "/notifications",
]


@pytest.mark.parametrize("path", LIST_PATHS)
async def test_b_lists_contain_nothing_of_a(tenants, path):
    a, b = tenants
    assert_nothing_of_a(await b.call("GET", path), a)


async def test_unbilled_endpoints_do_not_leak(tenants):
    a, b = tenants
    r = await b.call("GET", "/expenses/unbilled", params={"client_id": a.ids["client"]})
    assert_nothing_of_a(r, a)
    assert Decimal(str(r.json()["total"])) == 0
    r = await b.call("GET", "/time-entries/unbilled", params={"client_id": a.ids["client"]})
    assert_nothing_of_a(r, a)
    assert r.json() == []


async def test_b_settings_are_not_a_settings(tenants):
    a, b = tenants
    r = await b.call("GET", "/settings")
    assert r.status_code == 200
    assert r.json()["organization_id"] == b.org_id
    assert r.json()["invoice_prefix"] != "AAA"


# ---------------------------------------------------------------- writes

PAYMENT_BODY = {"amount": "1", "currency": "USD", "payment_date": TODAY, "payment_method": "Cash"}
WRITE_ATTEMPTS = [
    ("PATCH", "/clients/{client}", {"name": "hacked"}),
    ("DELETE", "/clients/{client}", None),
    ("PATCH", "/projects/{project}", {"name": "hacked"}),
    ("DELETE", "/projects/{project}", None),
    ("PATCH", "/expenses/{expense}", {"notes": "hacked"}),
    ("DELETE", "/expenses/{expense}", None),
    ("POST", "/expenses/{expense}/duplicate", None),
    ("POST", "/expenses/{expense}/status", {"status": "pending"}),
    ("PATCH", "/receipts/{receipt}", {"vendor": "hacked"}),
    ("DELETE", "/receipts/{receipt}", None),
    ("PATCH", "/time-entries/{time_entry}", {"description": "hacked"}),
    ("DELETE", "/time-entries/{time_entry}", None),
    ("PATCH", "/invoices/{invoice}", {"notes": "hacked"}),
    ("POST", "/invoices/{invoice}/status", {"status": "cancelled"}),
    ("POST", "/invoices/{invoice}/send", None),
    ("DELETE", "/invoices/{invoice}", None),
    ("POST", "/invoices/{invoice}/payments", PAYMENT_BODY),
    ("DELETE", "/payments/{payment}", None),
    ("PATCH", "/recurring-invoices/{recurring}", {"is_active": False}),
    ("POST", "/recurring-invoices/{recurring}/generate", None),
]
WRITE_IDS = [f"{m} {p}" for m, p, _ in WRITE_ATTEMPTS]


@pytest.mark.parametrize("method,template,body", WRITE_ATTEMPTS, ids=WRITE_IDS)
async def test_b_cannot_modify_a_records(tenants, method, template, body):
    a, b = tenants
    path = template.format(**a.ids)
    r = await b.call(method, path, json=body)
    assert r.status_code == 404, f"LEAK: B got {r.status_code} on {method} {path}: {r.text[:200]}"


async def test_b_cannot_upload_receipt_to_a_expense(tenants):
    a, b = tenants
    r = await b.call("POST", f"/expenses/{a.ids['expense']}/receipts",
                     files={"file": ("x.png", PNG_BYTES, "image/png")})
    assert r.status_code == 404


async def test_a_data_is_unchanged_after_b_attacks(tenants):
    a, b = tenants
    for method, template, body in WRITE_ATTEMPTS:
        await b.call(method, template.format(**a.ids), json=body)

    ids = a.ids
    assert must(await a.call("GET", f"/clients/{ids['client']}"), 200)["name"] == CLIENT_A
    assert must(await a.call("GET", f"/projects/{ids['project']}"), 200)["name"] == "Proj"
    expense = must(await a.call("GET", f"/expenses/{ids['expense']}"), 200)
    assert expense["notes"] is None and expense["vendor"] == VENDOR_A and expense["status"] == "draft"
    assert len(must(await a.call("GET", f"/expenses/{ids['expense']}/receipts"), 200)) == 1
    file_response = await a.call("GET", f"/receipts/{ids['receipt']}/file")
    assert file_response.status_code == 200 and file_response.content == PNG_BYTES
    assert must(await a.call("GET", f"/time-entries/{ids['time_entry']}"), 200)["description"] is None
    invoice = must(await a.call("GET", f"/invoices/{ids['invoice']}"), 200)
    assert invoice["status"] == "partially_paid" and invoice["notes"] is None
    must(await a.call("GET", f"/payments/{ids['payment']}"), 200)
    assert must(await a.call("GET", f"/recurring-invoices/{ids['recurring']}"), 200)["is_active"] is True


# ---------------------------------------------------------------- creating records that point at A's data

CROSS_REFERENCES = [
    ("POST", "/projects", lambda a, b: {"name": "x", "client_id": a.ids["client"], "billing_type": "fixed", "fixed_rate": "1"}, "INVALID_CLIENT"),
    ("POST", "/expenses", lambda a, b: {"client_id": a.ids["client"], "amount": "1", "expense_date": TODAY}, "INVALID_CLIENT"),
    ("POST", "/expenses", lambda a, b: {"client_id": b.ids["client"], "project_id": a.ids["project"], "amount": "1", "expense_date": TODAY}, "INVALID_PROJECT"),
    ("POST", "/expenses", lambda a, b: {"client_id": b.ids["client"], "category_id": a.ids["category"], "amount": "1", "expense_date": TODAY}, "INVALID_CATEGORY"),
    ("POST", "/time-entries", lambda a, b: {"client_id": a.ids["client"], "entry_date": TODAY, "duration_minutes": 30, "hourly_rate": "1"}, "INVALID_CLIENT"),
    ("POST", "/time-entries", lambda a, b: {"client_id": b.ids["client"], "project_id": a.ids["project"], "entry_date": TODAY, "duration_minutes": 30, "hourly_rate": "1"}, "INVALID_PROJECT"),
    ("POST", "/invoices", lambda a, b: {"client_id": a.ids["client"], "invoice_date": TODAY, "items": [{"description": "x", "unit_price": "1"}]}, "INVALID_CLIENT"),
    ("POST", "/invoices", lambda a, b: {"client_id": b.ids["client"], "invoice_date": TODAY, "expense_ids": [a.ids["expense"]]}, "INVALID_EXPENSE"),
    ("POST", "/invoices", lambda a, b: {"client_id": b.ids["client"], "invoice_date": TODAY, "time_entry_ids": [a.ids["time_entry"]]}, "INVALID_TIME_ENTRY"),
    ("POST", "/recurring-invoices", lambda a, b: {"client_id": a.ids["client"], "frequency": "monthly", "start_date": TODAY, "items": [{"description": "x", "unit_price": "1"}]}, "INVALID_CLIENT"),
]
CROSS_IDS = [f"{path} -> {code}" for _, path, _, code in CROSS_REFERENCES]


@pytest.mark.parametrize("method,path,build_body,expected_code", CROSS_REFERENCES, ids=CROSS_IDS)
async def test_b_cannot_attach_a_records(tenants, method, path, build_body, expected_code):
    a, b = tenants
    r = await b.call(method, path, json=build_body(a, b))
    assert r.status_code == 422, f"LEAK: B's request referencing A's data returned {r.status_code}: {r.text[:200]}"
    assert r.json()["error_code"] == expected_code


# ---------------------------------------------------------------- borrowing A's organization id

@pytest.mark.parametrize("method,path,body", [
    ("GET", "/clients", None), ("GET", "/expenses", None), ("GET", "/invoices", None),
    ("GET", "/dashboard", None), ("GET", "/reports/revenue", None),
    ("POST", "/clients", {"name": "sneaky"}),
])
async def test_b_cannot_use_a_org_id_header(tenants, method, path, body):
    a, b = tenants
    r = await b.call(method, path, org_id=a.org_id, json=body)
    assert r.status_code == 403
    assert r.json()["error_code"] == "NOT_A_MEMBER"


async def test_malformed_org_id_is_rejected(tenants):
    _, b = tenants
    r = await b.call("GET", "/clients", org_id="not-a-uuid")
    assert r.status_code == 422


# ---------------------------------------------------------------- dashboard, reports, exports

async def test_dashboard_shows_nothing_of_a_to_b(tenants):
    a, b = tenants
    control = must(await a.call("GET", "/dashboard"), 200)["totals"]  # proves the test data really exists
    assert Decimal(str(control["total_revenue"])) == 10
    assert Decimal(str(control["unbilled_expenses"])) == 25

    r = await b.call("GET", "/dashboard")
    assert_nothing_of_a(r, a)
    totals = r.json()["totals"]
    for key in ("total_revenue", "outstanding_invoices", "overdue_invoices",
                "expenses_this_month", "billable_expenses", "unbilled_expenses"):
        assert Decimal(str(totals[key])) == 0, f"LEAK: B's dashboard {key} = {totals[key]}"
    assert totals["paid_invoices_count"] == 0 and totals["pending_invoices_count"] == 0


@pytest.mark.parametrize("path", [
    "/reports/revenue", "/reports/expenses", "/reports/outstanding-invoices", "/reports/profitability",
])
async def test_reports_show_nothing_of_a_to_b(tenants, path):
    a, b = tenants
    assert_nothing_of_a(await b.call("GET", path), a)


@pytest.mark.parametrize("path", [
    "/reports/export/expenses.csv", "/reports/export/invoices.csv", "/reports/export/payments.csv",
])
async def test_csv_exports_show_nothing_of_a_to_b(tenants, path):
    a, b = tenants
    assert_nothing_of_a(await b.call("GET", path), a)


async def test_csv_export_control_a_sees_own_data(tenants):
    a, _ = tenants
    r = await a.call("GET", "/reports/export/expenses.csv")
    assert r.status_code == 200 and VENDOR_A in r.text


# ---------------------------------------------------------------- not logged in

@pytest.mark.parametrize("path", [
    "/clients", "/expenses", "/invoices", "/payments", "/dashboard", "/reports/revenue", "/notifications",
])
async def test_requests_without_login_are_rejected(path):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as anon:
        r = await anon.get(f"/api/v1{path}", headers={"X-Organization-Id": str(uuid.uuid4())})
    assert r.status_code == 401