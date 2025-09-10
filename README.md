# EcoWhiskey ATC Backend

A FastAPI-based Air Traffic Control training backend where pilot students can practice communicating with an ATC simulator. The service is built with Clean Architecture principles.

## Architecture

This project follows Clean Architecture patterns with clear separation of concerns:

```
app/
├── main.py                      # FastAPI app entry point and wiring
├── presentation/                # HTTP layer (routers, DTOs request/response)
│   ├── routers/
│   │   └── users.py            # User management endpoints
│   └── dtos.py                 # Data Transfer Objects
├── application/                 # Business logic layer
│   ├── use_cases/              # Application use cases
│   │   └── user_use_cases.py
│   └── interfaces.py           # Abstract interfaces
├── domain/                     # Core business entities
│   ├── models.py              # Domain models
│   └── services.py            # Domain services
├── infrastructure/             # External concerns
│   ├── persistence/
│   │   └── repositories_sqlalchemy.py
│   └── external/
│       ├── s3_adapter.py       # AWS S3 integration
│       └── mq_adapter.py       # Message Queue integration
└── config/                     # Configuration management
    ├── settings.py
    └── dependencies.py
```

## Features

- **Clean Architecture**: Clear separation between domain, application, infrastructure, and presentation layers
- **FastAPI**: Modern, fast web framework with automatic API documentation
- **Async/Await**: Full asynchronous support for high performance
- **SQLAlchemy**: ORM with async support for database operations
- **Pydantic**: Data validation and serialization
- **AWS S3 Integration**: File storage capabilities
- **Message Queue**: RabbitMQ integration for event-driven architecture
- **Environment Configuration**: Flexible configuration management
- **API Documentation**: Automatic OpenAPI/Swagger documentation

## Getting Started

### Prerequisites

- Python 3.9+
- PostgreSQL (optional, for persistence)
- RabbitMQ (optional, for message queuing)
- AWS S3 (optional, for file storage)

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

### User Management
- `POST /users` - Create user
- `GET /users/{user_id}` - Get user by ID
- `GET /users` - List all users
- `PUT /users/{user_id}` - Update user
- `DELETE /users/{user_id}` - Delete user

## Configuration

The application uses environment-based configuration. See `.env.example` for available options:

- Database settings (PostgreSQL)
- AWS S3 configuration
- RabbitMQ configuration
- JWT settings (for future authentication)
- CORS settings

## Clean Architecture Layers

### 1. Domain Layer
- **Models**: Core business entities (User)
- **Services**: Domain business rules and logic

### 2. Application Layer
- **Use Cases**: Application-specific business rules
- **Interfaces**: Abstract contracts for external dependencies

### 3. Infrastructure Layer
- **Repositories**: Data persistence implementations
- **External Services**: Third-party integrations (S3, RabbitMQ)

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
- **Boto3**: AWS S3 integration
- **Pika**: RabbitMQ client
- **Alembic**: Database migrations

## Development

### Project Structure Benefits

1. **Dependency Inversion**: Core business logic doesn't depend on external frameworks
2. **Testability**: Each layer can be tested independently
3. **Maintainability**: Clear boundaries and responsibilities
4. **Flexibility**: Easy to swap implementations (e.g., different databases)

### Adding New Features

1. **Domain First**: Define models and business rules in the domain layer
2. **Application Logic**: Create use cases in the application layer
3. **Infrastructure**: Implement repositories and external services
4. **Presentation**: Add API endpoints and DTOs

## Production Considerations

- Set up proper database with connection pooling
- Configure message queue for event processing
- Set up S3 bucket for file storage
- Implement authentication and authorization
- Add monitoring and logging
- Use environment-specific configurations
- Set up CI/CD pipelines

## License

This project is part of the EcoWhiskey ATC system.