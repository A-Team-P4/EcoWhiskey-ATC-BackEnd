# EcoWhiskey ATC Backend — Developer Guide

This guide explains how the backend is wired together, how requests flow through the layers, and how to extend the project with new database-backed endpoints. Use it alongside `README.md` when you need deeper implementation details.

## Architecture Recap

The service follows a Clean Architecture layout:

- **presentation** layer: FastAPI routers and DTOs that talk HTTP.
- **application** layer: use cases orchestrating domain logic.
- **domain** layer: entities and business rules, independent of frameworks.
- **infrastructure** layer: SQLAlchemy repositories that talk to the database.
- **config** layer: environment-driven configuration and dependency wiring.

```
Request → Router (FastAPI) → DTO validation → Use Case → Repository → Database
```

## Data Flow Walkthrough

The typical request/response sequence is illustrated below using the `POST /hello` endpoint as an example:

1. **FastAPI router** (`app/presentation/routers/hello.py`)
   - Validates the payload with `HelloMessageCreateRequest` and injects an async DB session via `get_database_session`.
2. **Use case** (`app/application/use_cases/hello_use_cases.py`)
   - `CreateHelloMessageUseCase` receives the business input and calls the repository.
3. **Repository** (`SQLAlchemyHelloMessageRepository` in `app/infrastructure/persistence/repositories_sqlalchemy.py`)
   - Persists the record using SQLAlchemy, returning a domain `HelloMessage`.
4. **Domain model** (`app/domain/models.py`)
   - Ensures data crossing boundaries uses well-defined entities (`HelloMessage`).
5. **DTO response** (`HelloMessageResponse`)
   - Serializes the domain model back to JSON for the caller.

Failures are raised as exceptions at any layer; routers translate them into HTTP responses (e.g., `HTTPException`).

## Database Connectivity

Configuration is centralized in `app/config/settings.py` using Pydantic settings:

- Set host, port, username, and database name in `.env` (prefixed `DB_`).
- Place sensitive secrets (e.g., `DB_PASSWORD`) in `.secrets/DB_PASSWORD` or inject them via environment variables in production. The file is ignored by Git.
- The async SQLAlchemy engine is created in `app/config/dependencies.py`, which also exposes `get_database_session`.
- `app/main.py` registers a FastAPI startup hook that calls `init_database_models()`, ensuring all SQLAlchemy metadata (including `hello_messages`) is present. You may skip this if you manage migrations with Alembic; just remove or replace the hook.

### Manual schema creation

The generated SQL for the hello-world table is:

```sql
CREATE TABLE IF NOT EXISTS hello_messages (
    id SERIAL PRIMARY KEY,
    message TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

Run it via `psql` if you prefer explicit migrations.

## Adding a New Endpoint

Use the checklist below to add a feature that reads/writes to the database:

1. **Domain** (`app/domain/`)
   - Define or update domain models to represent the new entity.

2. **Interfaces** (`app/application/interfaces.py`)
   - Add an abstract repository interface describing required persistence operations.

3. **Use cases** (`app/application/use_cases/`)
   - Implement one or more use case classes that depend only on interfaces.

4. **Infrastructure repository** (`app/infrastructure/persistence/`)
   - Extend `repositories_sqlalchemy.py` (or add a new module) with SQLAlchemy models inheriting from `Base`.
   - Implement the concrete repository that satisfies the interface and returns domain models.

5. **DTOs** (`app/presentation/dtos.py`)
   - Create request/response schemas for FastAPI validation and serialization.

6. **Router** (`app/presentation/routers/`)
   - Build a router module that constructs the repository + use case inside each endpoint handler.
   - Inject `AsyncSession` using `Depends(get_database_session)`.

7. **Wire it up** (`app/main.py`)
   - Import and register the new router with `app.include_router(...)`.

8. **Database migrations**
   - If new tables/columns are required, update SQLAlchemy entities and run migrations (or rely on `init_models` in dev setups).

9. **Tests (recommended)**
   - Add tests targeting use cases and routers with mocked repositories or a test database.

## File Reference

Below is a quick map of the key files and what they do:

- `app/main.py` — Creates the FastAPI app, registers routers/middleware, and ensures DB metadata exists on startup.
- `app/config/settings.py` — Pydantic settings for environment configuration (database, AWS Polly, CORS).
- `app/config/dependencies.py` — Builds the async SQLAlchemy engine, session factory, and exposes helpers (`get_database_session`, `init_database_models`).
- `app/domain/models.py` — Domain entities (`User`, `HelloMessage`, etc.) that represent core business objects.
- `app/application/interfaces.py` — Abstract interfaces for repositories (users, hello messages).
- `app/application/use_cases/` — Business workflows such as `CreateUserUseCase` and `CreateHelloMessageUseCase`.
- `app/infrastructure/persistence/repositories_sqlalchemy.py` — SQLAlchemy ORM models plus concrete repository implementations and metadata initialization.
- `app/presentation/dtos.py` — Request/response schemas shared across routers.
- `app/presentation/routers/` — FastAPI routers for HTTP endpoints (`users`, `hello`, `tts`, `test`).
- `run.py` or `uvicorn` command — Entry point for local development (`uvicorn app.main:app --reload`).
- `.env` / `.secrets/` — Environment configuration and sensitive credentials (ignored by Git).

## Tips & Conventions

- Keep business rules inside the domain and application layers; routers should stay thin.
- Sanitize/validate external input using DTOs before it reaches use cases.
- Return domain models from repositories and transform them into DTOs at the presentation layer.
- For production, manage schema changes with Alembic migrations instead of relying solely on `init_models`.
- Prefer dependency injection through FastAPI `Depends` for sessions and service objects; it keeps handlers easy to test.

Have questions? Start by inspecting the `hello` router alongside this guide—it is the smallest end-to-end example of the recommended flow.
