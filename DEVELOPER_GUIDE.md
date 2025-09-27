# EcoWhiskey ATC Backend — Developer Guide

This guide explains how the MVC-style backend is wired together, how requests travel through controllers, views, and models, and how to extend the project with new database-backed endpoints. Keep it alongside `README.md` for quick reference.

## Architecture Recap

- **Controllers** (`app/controllers/`): FastAPI routers coordinate requests, interact with the database session, and return view objects.
- **Views** (`app/views/`): Pydantic schemas validate incoming payloads and serialise outgoing responses.
- **Models** (`app/models/`): SQLAlchemy ORM classes map Python objects to PostgreSQL tables.
- **Shared utilities**: `app/database.py` manages the async engine/session lifecycle; `app/config/settings.py` centralises configuration via Pydantic settings.

```
Request → Controller (FastAPI) → View validation → Model persistence → View response → JSON
```

## Data Flow Walkthrough (`POST /hello`)

1. **Controller** — `app/controllers/hello.py` receives the request, depends on `get_session()` from `app/database.py`, and instantiates a `HelloMessage` model.
2. **Model** — `app/models/hello.py` defines the SQLAlchemy table; the controller adds an instance and commits the async session.
3. **View** — `HelloMessageRead` in `app/views/hello.py` converts the SQLAlchemy object into a JSON-friendly payload returned to the client.

Errors bubble up as exceptions; controllers catch and translate them into `HTTPException` responses where appropriate.

## Database Connectivity

- Configure credentials in `.env` (`DB_HOST`, `DB_PORT`, `DB_USERNAME`, `DB_DATABASE`). Keep secrets like `DB_PASSWORD` in `.secrets/DB_PASSWORD` or inject them via environment variables in production.
- `app/database.py` builds the async SQLAlchemy engine and session factory using `settings.database.url`.
- The FastAPI startup hook in `app/main.py` calls `init_models()` so tables defined in `app/models/` are created automatically during development (swap for migrations such as Alembic in production).

### Manual schema creation

```sql
CREATE TABLE IF NOT EXISTS hello_messages (
    id SERIAL PRIMARY KEY,
    message TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

Run via `psql` if you prefer explicit DDL execution.

## Adding a New Endpoint (MVC Checklist)

1. **Model** — Define or update a SQLAlchemy model in `app/models/` (remember to import it in `app/models/__init__.py` if new).
2. **View** — Create request/response Pydantic models in `app/views/`.
3. **Controller** — Add FastAPI routes in `app/controllers/`, injecting an `AsyncSession` with `Depends(get_session)` from `app/database.py`.
4. **Wire-up** — Register the router in `app/main.py` using `app.include_router(...)`.
5. **Schema management** — For development the startup hook creates tables; for production prefer migrations.
6. **Tests (recommended)** — Test controllers with the FastAPI test client and a transactional database fixture.

## File Reference

- `app/main.py` — Configures FastAPI, middleware, startup tasks, and router registration.
- `app/database.py` — Async SQLAlchemy engine/session factory and `init_models()` helper.
- `app/config/settings.py` — Pydantic settings for app metadata, database, S3/Polly, and CORS.
- `app/controllers/*.py` — Route handlers (users, hello, tts, test) acting as controllers.
- `app/views/*.py` — Pydantic schemas used for validation and serialisation.
- `app/models/*.py` — SQLAlchemy ORM models representing database tables.
- `.secrets/` & `.env` — Environment configuration and sensitive credentials (ignored by Git).

## Tips & Conventions

- Keep controllers thin: validate/serialise with views and delegate persistence to SQLAlchemy models.
- Prefer `UserRead.model_validate(db_user)` (Pydantic v2) to transform ORM objects into responses.
- When adding models, ensure they are imported somewhere under `app/models/__init__.py` so metadata loads before `init_models()` is called.
- For production deployments, disable the automatic table creation and manage schema changes through migrations.
- Reuse the shared async session dependency to keep database access consistent and testable.

Need inspiration? The `/hello` controller is the smallest end-to-end example covering model creation, persistence, and view responses in this MVC setup.
