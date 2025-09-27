# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Running the Application
```bash
python run.py
# OR
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Linting and Code Quality
```bash
# Install linting tools
pip install flake8 flake8-bugbear flake8-import-order black isort

# Run all linting checks
flake8 .
black --check .
isort --check-only .

# Auto-format code
black .
isort .
```

### Dependencies
```bash
pip install -r requirements.txt
```

## Architecture Overview

This is a FastAPI-based Air Traffic Control training backend with an MVC-style architecture:

- **Controllers** (`app/controllers/`): FastAPI routers that handle HTTP requests and coordinate business logic
- **Models** (`app/models/`): SQLAlchemy ORM models for database persistence
- **Views** (`app/views/`): Pydantic schemas for request/response validation and serialization
- **Configuration** (`app/config/settings.py`): Environment-driven configuration using Pydantic settings
- **Database** (`app/database.py`): Async SQLAlchemy engine and session management

### Request Flow
```
HTTP Request → Controller → View validation → Model persistence → View response → JSON Response
```

### Key Files
- `app/main.py`: FastAPI app configuration, middleware setup, and router registration
- `app/database.py`: Database session factory and async engine setup
- `run.py`: Application entry point for development

## Database Configuration

The application uses PostgreSQL with async SQLAlchemy. Configure via environment variables:
- `DB_HOST`, `DB_PORT`, `DB_USERNAME`, `DB_DATABASE` in `.env`
- `DB_PASSWORD` should be in `.secrets/DB_PASSWORD` or environment variable

Tables are auto-created on startup in development mode via the `init_models()` function.

## Environment Setup

1. Copy `.env.example` to `.env` and configure
2. Set up `.secrets/DB_PASSWORD` for database password
3. Configure AWS credentials for Polly TTS integration (optional)

## Adding New Features (MVC Pattern)

1. **Model**: Define SQLAlchemy model in `app/models/` and import in `__init__.py`
2. **View**: Create Pydantic schemas in `app/views/` for request/response
3. **Controller**: Add FastAPI routes in `app/controllers/` with `Depends(get_session)` for database access
4. **Wire-up**: Register new router in `app/main.py` using `app.include_router()`

## Code Style

- Use Black formatter with 88 character line length
- Import sorting with isort (Black profile)
- Flake8 linting with specific ignore rules (E203, W503)
- Follow snake_case for functions/modules, PascalCase for classes
- Use conventional commits for version control

## Testing

The project uses the CI workflow in `.github/workflows/ci.yml` which runs linting on push/PR.