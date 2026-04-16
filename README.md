<div align="center">
  <img src="./dentora.png" alt="Dentora Logo" width="200" />
  <h1>Dentora</h1>
  <p><strong>Backend for dental appointment management</strong></p>
</div>

## Stack

- **Runtime**: Python 3.12+
- **Framework**: Django 5.1 + Django REST Framework
- **Database**: PostgreSQL
- **Task Queue**: Celery + Redis
- **Dependency Management**: Poetry
- **Containerization**: Docker + docker-compose
- **Testing**: pytest + factory_boy
- **Code Quality**: black, flake8, mypy
- **API Documentation**: drf-spectacular (Swagger/OpenAPI)

## Quick Start

### 1. Install Dependencies

```bash
poetry install
```

### 2. Setup Environment

```bash
cp .env.example .env
```

Edit `.env` if needed (defaults work for local development).

### 3. Start Services

```bash
docker-compose up -d
```

Waits for PostgreSQL and Redis to be ready, then:

### 4. Initialize Database

```bash
poetry run python manage.py migrate
poetry run python manage.py createsuperuser
```

### 5. Run Server

```bash
poetry run python manage.py runserver
```

Access:
- **API**: http://localhost:8000/api/
- **Swagger UI**: http://localhost:8000/api/docs/
- **Admin**: http://localhost:8000/admin/

### 6. Run Celery Worker (in a separate terminal)

```bash
poetry run celery -A dentora worker --loglevel=info
```

---

## Commands

### Development

```bash
# Start all services (DB, Redis, app, Celery worker)
docker-compose up

# Run server in development mode
poetry run python manage.py runserver

# Run Celery worker
poetry run celery -A dentora worker --loglevel=info

# Access Django shell
poetry run python manage.py shell
```

### Database

```bash
# Create migrations
poetry run python manage.py makemigrations

# Apply migrations
poetry run python manage.py migrate

# Show migration status
poetry run python manage.py showmigrations

# Revert migrations
poetry run python manage.py migrate <app> <migration_number>
```

### Testing

```bash
# Run all tests
poetry run pytest

# Run tests with coverage
poetry run pytest --cov --cov-report=term-missing

# Run specific test file
poetry run pytest -x -k "test_name"

# Stop on first failure
poetry run pytest -x
```

### Code Quality

**Must pass all checks before committing:**

```bash
# Format code
poetry run black .

# Lint code
poetry run flake8 .

# Type check
poetry run mypy .
```

---

## Architecture

### App Structure

Each domain lives in its own Django app. Do not import models across apps except through services.

```
dentora/
├── config/              # Settings, URLs, WSGI, ASGI, Celery
├── core/                # Shared utilities, base classes, exceptions
├── appointments/        # Booking, cancellation, rescheduling
├── patients/            # Patient profiles
├── dentists/            # Dentist profiles, availability
└── notifications/       # Email/SMS reminders via Celery
```

### Layer Responsibilities

| Layer | Responsibility |
|-------|----------------|
| `models.py` | Data shape, constraints, relationships |
| `serializers.py` | Input validation, data transformation |
| `views.py` | HTTP contract, permissions, orchestration |
| `services.py` | Business logic, domain rules, transactions |
| `tasks.py` | Async workers, deferred side effects |
| `permissions.py` | Custom DRF permission classes |
| `tests/` | Unit and integration tests |

---

## Code Standards

### Formatting & Linting

- **Formatter**: black (line length 88) — no manual formatting
- **Linter**: flake8 — fix all warnings before committing
- **Type Checker**: mypy strict mode — annotate all function signatures

### Serializers

- Never use `fields = '__all__'`
- Separate serializers for different use cases (e.g., `AppointmentCreateSerializer`, `AppointmentReadSerializer`)

### Views

- Use `APIView` or `GenericAPIView` for non-trivial business logic
- Use `ModelViewSet` only for simple CRUD
- Always declare `permission_classes` and `authentication_classes` explicitly
- Annotate every endpoint with `@extend_schema`

### Services

- Plain Python functions/classes in `services.py`
- Raise domain-level exceptions from `core/exceptions.py`
- Wrap multi-step DB operations in `transaction.atomic()`
- One service function = one responsibility

### Celery Tasks

- Must be idempotent where possible
- Call service functions, not inline business logic
- Always set `bind=True` and handle retries explicitly
- Log task start, completion, and failures

---

## API Documentation

Every endpoint must have `@extend_schema` annotation:

```python
@extend_schema(
    summary="Create a new appointment",
    responses=AppointmentSerializer,
)
def post(self, request):
    ...
```

View the schema at:
- **OpenAPI JSON**: http://localhost:8000/api/schema/
- **Swagger UI**: http://localhost:8000/api/docs/

---

## Testing

### Structure

```
<app>/tests/
├── __init__.py
├── factories.py          # Data factories (factory_boy)
├── test_models.py        # Model tests
├── test_serializers.py   # Serializer tests
├── test_views.py         # Integration tests (HTTP)
└── test_services.py      # Unit tests (business logic)
```

### Rules

- Use factories for all test data
- Test happy path + validation errors + important failure cases
- Use real test DB (pytest-django manages it)
- Mark DB-hitting tests with `@pytest.mark.django_db`
- Do not hardcode PKs or magic strings

---

## Migrations

- One migration per coherent change
- Never edit existing migrations — create new ones
- Separate data migrations from schema migrations
- Every `RunPython` must have a reverse function
- Check for table locks before production deployment

---

## Before Marking a Task Done

1. `poetry run black .` — no diffs
2. `poetry run flake8 .` — no errors  
3. `poetry run mypy .` — no new errors
4. `poetry run pytest -x` — all tests pass
5. New code has at least one test
6. New endpoints have `@extend_schema` with summary + responses
7. Migrations: only new ones created, never edited

---

## Environment Variables

See `.env.example` for all required variables:

- `DEBUG`: True for development, False for production
- `SECRET_KEY`: Django secret key (generate with `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`)
- `ALLOWED_HOSTS`: Comma-separated list
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection URL
- `CELERY_BROKER_URL`: Redis for Celery broker
- `CELERY_RESULT_BACKEND`: Redis for Celery results

---

## Troubleshooting

### PostgreSQL connection fails

```bash
# Check if services are running
docker-compose ps

# View logs
docker-compose logs db
docker-compose logs app
```

### Celery tasks not running

```bash
# Check Celery worker logs
docker-compose logs celery

# Verify Redis is running
redis-cli ping
```

### Migrations fail

```bash
# Show migration status
poetry run python manage.py showmigrations

# Revert to previous migration
poetry run python manage.py migrate <app> <previous_number>
```

### Tests fail

```bash
# Run with verbose output
poetry run pytest -v -s

# Run specific test
poetry run pytest -x -k "test_function_name"
```

---

## Support

For detailed architectural guidelines, see [CLAUDE.md](./CLAUDE.md).
