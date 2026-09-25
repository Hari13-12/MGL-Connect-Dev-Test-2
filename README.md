# MGL Connect

MGL Connect is a **FastAPI backend service** for the MGL Connect PWA, including its admin panel (served from the same versioned API, gated by role-based access).

## Project structure

```
app/
├── main.py                # FastAPI app factory, lifespan, middleware, router registration
├── core/                  # Cross-cutting concerns
│   ├── config.py          # Settings (env-driven)
│   ├── logging.py         # Logging configuration
│   └── exceptions.py      # Global exception handlers
├── database/
│   ├── base.py            # Declarative Base, async engine, connection check
│   └── session.py         # get_db() dependency (per-request AsyncSession)
├── models/                # SQLAlchemy ORM models (one file per domain entity)
├── schemas/                # Pydantic request/response schemas (one file per domain entity)
├── api/
│   └── v1/
│       ├── api.py         # Aggregates all v1 routers into api_router
│       └── routes/        # One module per resource (health_route.py, user_route.py, ...)
│           └── admin/     # Admin-only routes, protected by a role dependency
└── services/               # Business logic (user_service.py, ...), called by routes, calling repositories/models

tests/
├── conftest.py            # Shared fixtures (async test client, env setup)
└── test_*.py               # One test module per route/service module
```

Routes are versioned (`/api/v1/...`) so a future `v2` can be introduced without breaking existing clients (mobile PWA, admin). Admin-only endpoints live alongside public ones under `api/v1/routes/admin/`, protected by a role-check dependency in `api/v1/deps.py` once auth is introduced — not a separate service.

## Naming conventions

- Files/modules: `snake_case.py`, suffixed by layer so the file's role is obvious from its name alone:
  - Routes: `<resource>_route.py` (e.g. `health_route.py`, `user_route.py`)
  - Services: `<resource>_service.py` (e.g. `user_service.py`)
  - Models: `<resource>.py` under `models/` (e.g. `user.py`)
  - Schemas: `<resource>.py` under `schemas/` (e.g. `user.py`)
- Classes: `PascalCase` (`UserService`, `UserCreate`).
- Functions/variables: `snake_case`.
- Constants/settings: `UPPER_SNAKE_CASE`.
- One router per resource file; routers are combined in `api/v1/api.py`, not registered directly on `app` in `main.py`.
- Pydantic schemas mirror model names with a suffix for intent: `UserCreate`, `UserRead`, `UserUpdate`.

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/Appstrail-Technology/MGL-Connect-Backend-service.git
cd MGL-Connect-Backend-service
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt        # production
pip install -r requirements-dev.txt    # local dev + testing (includes the above)
```

### 4. Configure environment

Copy `.env.example` to `.env` and fill in real values:

```bash
cp .env.example .env
```

### 5. Run the server

```bash
uvicorn app.main:app --reload
```

## Testing

```bash
pytest
```

Tests use an in-process ASGI client (`httpx.AsyncClient` + `ASGITransport`), so they don't require a running server. External calls (e.g. the database health check) are mocked at the boundary — see `tests/test_health.py`.

## Deployment (Heroku)

- Python version is pinned via `.python-version` (major version only, e.g. `3.13`) — `runtime.txt` is deprecated by Heroku's Python buildpack and has been removed.
- `Procfile` runs Gunicorn with the Uvicorn worker class: `gunicorn app.main:app --workers 4 --worker-class uvicorn_worker.UvicornWorker --bind 0.0.0.0:$PORT`.
- Required config vars (see `.env.example`): `DATABASE_USER`, `DATABASE_PASSWORD`, `DATABASE_HOST`, `DATABASE_PORT`, `DATABASE_NAME`, `DATABASE_SCHEMA`, `APP_NAME`, `APP_VERSION`, `VERSION`, `DEBUG`.
