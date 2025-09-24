# EcoWhiskey ATC Backend

A FastAPI-based Air Traffic Control training backend where pilot students can practice communicating with an ATC simulator. The service is built with Clean Architecture principles.

## Architecture Decisions

- **General**: Monolithic application.
- **Internal**: Clean Architecture with presentation, application, domain and infrastructure layers.

## Project Structure

This project follows Clean Architecture patterns with clear separation of concerns:

```
app/
├── main.py                      # FastAPI app entry point and wiring
├── presentation/                # HTTP layer (routers, DTOs request/response)
│   ├── routers/
│   │   ├── hello.py            # Example hello-world endpoints
│   │   ├── test.py             # Lightweight diagnostics
│   │   ├── tts.py              # Text-to-speech endpoint
│   │   └── users.py            # User management endpoints
│   └── dtos.py                 # Data Transfer Objects
├── application/                 # Business logic layer
│   ├── use_cases/              # Application use cases
│   │   ├── hello_use_cases.py
│   │   └── user_use_cases.py
│   └── interfaces.py           # Abstract interfaces
├── domain/                     # Core business entities
│   ├── models.py              # Domain models
│   └── services.py            # Domain services
├── infrastructure/             # Persistence and integration points
│   └── persistence/
│       └── repositories_sqlalchemy.py
└── config/                     # Configuration management
    ├── settings.py
    └── dependencies.py
```

## Features

- **Clean Architecture**: Clear separation between presentation, application, domain, and infrastructure layers
- **FastAPI**: Modern, fast web framework with automatic API documentation
- **Async/Await**: Full asynchronous support for high performance
- **SQLAlchemy + Pydantic**: Async persistence paired with strict validation
- **AWS Polly**: Text-to-speech conversion via `boto3`
- **Hello-world example**: End-to-end sample feature worth mirroring
- **Environment Configuration**: Flexible configuration management

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

## Clean Architecture Layers

### 1. Domain Layer
- **Models**: Core business entities (User)
- **Services**: Domain business rules and logic

### 2. Application Layer
- **Use Cases**: Application-specific business rules
- **Interfaces**: Abstract contracts for external dependencies

### 3. Infrastructure Layer
- **Repositories**: Data persistence implementations

### 4. Presentation Layer
- **Routers**: HTTP request handling
- **DTOs**: Request/Response data structures

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

### Project Structure Benefits

1. **Dependency Inversion**: Core business logic doesn't depend on external frameworks
2. **Testability**: Each layer can be tested independently
3. **Maintainability**: Clear boundaries and responsibilities
4. **Flexibility**: Easy to swap implementations (e.g., different databases)

### Adding New Features

1. **Domain First**: Define models and business rules in the domain layer
2. **Application Logic**: Create use cases in the application layer
3. **Infrastructure**: Implement repositories (and other integrations if required)
4. **Presentation**: Add API endpoints and DTOs

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
