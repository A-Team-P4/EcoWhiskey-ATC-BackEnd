# EcoWhiskey ATC Backend

A FastAPI-based Air Traffic Control training backend where pilot students can practise communicating with an ATC simulator. The project is organised with a lightweight MVC-style structure to keep the learning curve gentle.

## Architecture Decisions

- **General**: Monolithic application.
- **Internal**: Basic MVC (controllers ↔ views ↔ models) with shared configuration utilities.

## Project Structure

```
app/
├── main.py                 # FastAPI app configuration and router wiring
├── database.py             # Async SQLAlchemy engine, session factory, metadata init
├── config/
│   └── settings.py        # Environment-driven configuration (Pydantic)
├── controllers/           # FastAPI routers acting as controllers
│   ├── hello.py
│   ├── test.py
│   ├── tts.py
│   └── users.py
├── models/                # SQLAlchemy models (data layer)
│   ├── __init__.py
│   ├── hello.py
│   └── user.py
└── views/                 # Pydantic schemas returned by controllers (view layer)
    ├── __init__.py
    ├── common.py
    ├── hello.py
    ├── tts.py
    └── users.py
```

## Features

- **MVC layout**: Controllers manage routing, models handle persistence, and views (Pydantic schemas) shape the payloads.
- **FastAPI + Async SQLAlchemy**: High-performance async stack with idiomatic dependency injection.
- **AWS Polly integration**: Text-to-speech conversion via `boto3` with simple configuration.
- **Hello-world sample**: `/hello` endpoints demonstrate an end-to-end create/list workflow.
- **Environment configuration**: `.env` + `.secrets` support through typed Pydantic settings.

## Getting Started

### Prerequisites

- Python 3.9+
- PostgreSQL (optional, for persistence)
- AWS credentials with Polly access (optional, for text-to-speech)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd EcoWhiskey-ATC-BackEnd
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

### Running the Application

1. Start the development server:
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

2. Access the application:
- API: http://localhost:8000
- Documentation: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpoints

### Core Endpoints
- `GET /` - Welcome message
- `GET /health` - Health check
- `GET /test/health` - Test health check

### User Management
- `POST /users` - Create user
- `GET /users/{user_id}` - Get user by ID
- `GET /users` - List all users
- `PUT /users/{user_id}` - Update user
- `DELETE /users/{user_id}` - Delete user

## Configuration

The application uses environment-based configuration. See `.env.example` for available options:

- Database settings (PostgreSQL)
- AWS configuration (Polly region and optional credentials)
- CORS settings

### Database credentials

- Set `DB_HOST`, `DB_PORT`, `DB_USERNAME`, and `DB_DATABASE` in `.env` to match your PostgreSQL instance.
- Keep the password out of `.env` in production; create a `.secrets/DB_PASSWORD` file (or equivalent secret store) containing only the password.
- For containerized or cloud deployments, inject the password via environment variables or a secrets manager (e.g., AWS Secrets Manager) instead of committing it to the repository.

## MVC Request Flow

1. **Controller** — FastAPI routers in `app/controllers/` receive the HTTP request, validate inputs, and obtain an async database session via `app/database.py`.
2. **View** — Pydantic schemas in `app/views/` validate inbound payloads and transform SQLAlchemy model instances into JSON-safe responses.
3. **Model** — SQLAlchemy models in `app/models/` persist or fetch data using the shared async session.
4. **Response** — Controllers return view objects, and FastAPI serialises them as the HTTP response.

## Dependencies

### Core Dependencies
- **FastAPI**: Web framework
- **Uvicorn**: ASGI server
- **Pydantic**: Data validation
- **SQLAlchemy**: ORM with async support
- **AsyncPG**: PostgreSQL async driver

### External Service Dependencies
- **Boto3**: AWS Polly integration
- **Alembic**: Database migrations (optional)

## Development

### Adding New Features (MVC)

1. **Model** — Define or update SQLAlchemy models in `app/models/`.
2. **View** — Create Pydantic request/response schemas in `app/views/`.
3. **Controller** — Add FastAPI routes in `app/controllers/`, injecting the async session with `Depends(get_session)`.
4. **Wire-up** — Register the new router in `app/main.py`.

## Production Considerations

- Set up proper database with connection pooling
- Provide AWS credentials for Polly if the TTS endpoint is needed
- Implement authentication and authorization
- Add monitoring and logging
- Use environment-specific configurations
- Set up CI/CD pipelines

## Diagrams

The following diagrams are available in `docs/diagrams/`:

- Context Diagram (C4 Level 1)
- Component Diagram (C4 Level 2-3)
- User Flow

## Development Standards

### Branch Strategy
- `main`: stable production code
- `develop`: integration branch
- `feature/*`: short-lived feature branches

### Commit Convention
- [Conventional Commits](https://www.conventionalcommits.org/)

### Naming
- Classes: `PascalCase`
- Functions/Modules: `snake_case`
- Endpoints: RESTful and kebab-case

## Linting & Formatting

Install tools:

```bash
pip install flake8 flake8-bugbear flake8-import-order black isort
```

Run checks:

```bash
flake8 .
black --check .
isort --check-only .
```

## CI/CD

GitHub Actions workflow runs lint checks on every push and pull request (`.github/workflows/ci.yml`).

## Definition of Done

- Code reviewed by at least one teammate.
- Linting passes.
- Tests (if any) pass.
- Documentation updated.

## License

This project is part of the EcoWhiskey ATC system.
