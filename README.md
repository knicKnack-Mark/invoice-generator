# Backend — VA Invoice & Expense Tracker

## Setup (no Docker)

1. Create a virtualenv and install deps:
   ```
   python3 -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Copy `.env.example` to `.env` and set `DATABASE_URL` to your Supabase pooler
   connection string, plus a random `JWT_SECRET`.
3. Run migrations:
   ```
   alembic upgrade head
   ```
4. Start the server:
   ```
   uvicorn app.main:app --reload
   ```
5. Open http://localhost:8000/docs — try `GET /api/v1/health/db` first to
   confirm the Supabase connection, then `POST /api/v1/auth/register`.

## What's included in this slice

- `users`, `refresh_tokens`, `organizations`, `organization_members` tables
  (migration `0001_foundation.py`)
- Full auth flow: register (creates a user **and** their first organization
  as `owner`), login, refresh, logout, `/auth/me`
- `GET /api/v1/organizations` — list the organizations the current user
  belongs to
- `get_current_user` / `get_current_membership` dependencies in
  `app/core/deps.py` — this is the tenant-isolation enforcement point every
  future org-scoped route (clients, expenses, invoices...) will depend on
- Consistent `{success, data|message, error_code}` response envelope and
  centralized exception handling in `app/main.py`

## Not included yet (later phases)

Email verification / password reset emails, 2FA, rate limiting, clients,
projects, expenses, receipts, invoices, payments — these follow the same
model → migration → schema → repository → service → routes → tests pattern
already established here.

## What's new in this update

- **Clients module** — full CRUD (`POST/GET/PATCH/DELETE /api/v1/clients`),
  soft delete, pagination, search, status filter. Migration `0002_clients.py`.
- **Everything configurable is in `.env`** — app name/version, API prefix,
  pagination defaults, rate-limit thresholds. Nothing is hard-coded in routes
  or services; `app/main.py` reads `settings.app_name` for the API title,
  `clients.py` reads `settings.default_page_size`, etc.
- **`GET /api/v1/ping`** — unauthenticated, no DB/Redis dependency. Point the
  frontend at this for a pure "can I reach the backend at all" check, and at
  `GET /api/v1/health/db` for a "is the database also reachable" check.
- **Rate limiting** — Redis-backed fixed-window limiter
  (`app/middleware/rate_limit.py`), applied globally. `/auth/login` and
  `/auth/register` get a stricter limit (`RATE_LIMIT_AUTH_PER_MINUTE`,
  default 10/min) than the rest of the API (`RATE_LIMIT_PER_MINUTE`, default
  60/min). Returns `429` with the same `{success, message, error_code}`
  envelope. Fails open if Redis is unreachable so a cache outage never takes
  the API down.
- **SQL injection**: every query in every repository goes through SQLAlchemy's
  Core/ORM query builder with bound parameters (`Client.name.ilike(...)`,
  `.where(Client.id == client_id)`, etc.) — there is no raw string-formatted
  SQL anywhere in the codebase, which is what actually prevents injection,
  not a WAF or input sanitizer bolted on afterward.
- **Every business endpoint requires two things**: a valid access-token
  cookie (`get_current_user`) and active membership in the organization named
  by the `X-Organization-Id` header (`get_current_membership` /
  `require_role`). `/ping`, `/health`, `/health/db` are the only public routes.

## What's new: Projects module

- `POST/GET/PATCH/DELETE /api/v1/projects` — same auth/role/tenant pattern as
  clients. Migration `0003_projects.py`.
- Every project must reference a `client_id` belonging to the **same**
  organization — enforced in `ProjectService.create` via
  `ProjectRepository.client_exists(organization_id=..., client_id=...)`.
  Attempting to attach a project to another org's client returns `422
  INVALID_CLIENT`, not a silent success or a 500. Covered by
  `tests/test_projects.py::test_project_requires_client_in_same_org`.
- Billing-type/rate consistency (`hourly` requires `hourly_rate`,
  `fixed`/`retainer` require `fixed_rate`) is enforced in the Pydantic schema
  itself (`ProjectCreate.check_dates_and_rates`), so bad data never reaches
  the service or database layer.

## What's new: security hardening (CSRF, lockout, audit/activity logs, headers)

- **CSRF protection** — double-submit cookie pattern (`app/middleware/csrf.py`).
  On login/register/refresh the backend sets a `csrf_token` cookie that is
  readable by frontend JS (not httpOnly, unlike the auth cookies). The
  frontend must read that cookie and echo it back in an `X-CSRF-Token` header
  on every state-changing request (POST/PATCH/PUT/DELETE) except
  login/register/refresh themselves. A missing or mismatched token returns
  `403 CSRF_VALIDATION_FAILED`.
- **Security headers** — `app/middleware/security_headers.py` adds
  `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`,
  `Referrer-Policy`, `Permissions-Policy`, and `Strict-Transport-Security`
  (non-development only) to every response.
- **Per-account login lockout** — separate from the IP-based rate limiter.
  After `LOGIN_LOCKOUT_THRESHOLD` (default 5) failed attempts for the same
  email within `LOGIN_LOCKOUT_MINUTES` (default 15), further attempts return
  `423 ACCOUNT_LOCKED` even from a different IP. Tracked in Redis
  (`app/integrations/login_lockout.py`); fails open if Redis is unreachable.
- **Audit logs** (`audit_logs` table, migration `0004`) — append-only record
  of sensitive actions: register, login, login_failed, logout, client/project
  deletion. Each row has `user_id`, `organization_id`, `action`, `entity_id`,
  `ip_address`. In production, revoke UPDATE/DELETE on this table from your
  application's DB role (see the comment in the migration) so even a
  compromised app can't rewrite its own history.
- **Activity logs** (`activity_logs` table, same migration) — everyday
  create/update actions on clients and projects, for an in-app timeline.
- All of the above is wired into the existing Clients and Projects modules
  end to end, not just scaffolded — `ClientService`/`ProjectService` now
  take an `actor_user_id` and write the appropriate log on every mutation.

### Frontend implication (CSRF)

After a successful login/register/refresh response, read the `csrf_token`
cookie value client-side and send it as `X-CSRF-Token` on every subsequent
POST/PATCH/PUT/DELETE. Example with fetch:

```js
function getCookie(name) {
  return document.cookie.split('; ').find(r => r.startsWith(name + '='))?.split('=')[1];
}

fetch('/api/v1/clients', {
  method: 'POST',
  credentials: 'include',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRF-Token': getCookie('csrf_token'),
  },
  body: JSON.stringify({ name: 'Acme Corp' }),
});
```

## Redis: Upstash REST support

`app/integrations/redis_client.py` now supports two ways to connect:

1. **Upstash REST API** (recommended if you're on Upstash's free tier and
   don't want to hunt for the TCP connection string) — set
   `UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_TOKEN` in `.env` (both
   values are shown directly on your Upstash database's dashboard). The app
   detects these and uses `upstash-redis`'s async REST client automatically.
2. **Standard Redis URL** — set `REDIS_URL` to any `redis://` or `rediss://`
   connection string (local Redis, Upstash's TCP endpoint, or any other
   provider). Used only if the Upstash REST vars above are not set.

Both expose the same `get`/`set`/`incr`/`expire`/`delete` interface, so
`app/middleware/rate_limit.py` and `app/integrations/login_lockout.py` work
identically regardless of which one is active.
