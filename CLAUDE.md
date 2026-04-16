# Dentora

Backend for dental appointment management.

## Stack

- **Runtime**: Python 3.12+
- **Framework**: Django + Django REST Framework
- **Database**: PostgreSQL
- **Async tasks**: Celery + Redis
- **Dependencies**: Poetry
- **Infrastructure**: Docker + docker-compose
- **Testing**: pytest + factory_boy
- **Code quality**: black, flake8, mypy
- **API docs**: drf-spectacular (Swagger / OpenAPI)

## Common commands

```bash
# Start services
docker-compose up -d

# Run server
poetry run python manage.py runserver

# Tests
poetry run pytest
poetry run pytest -x                          # stop on first failure
poetry run pytest -x -k "test_name"           # run specific test
poetry run pytest --cov --cov-report=term-missing

# Code quality (run in this order)
poetry run black .
poetry run flake8 .
poetry run mypy .

# Database
poetry run python manage.py makemigrations
poetry run python manage.py migrate
poetry run python manage.py showmigrations
```

---

## Architecture

### App layout

Each domain lives in its own Django app. Do not create cross-domain model imports unless strictly necessary.

```
dentora/
  config/           # settings, urls, wsgi, asgi
  core/             # shared utilities, base classes, exceptions
  appointments/     # turnos: booking, cancellation, rescheduling
  patients/         # patient profiles
  dentists/         # dentist profiles, availability
  notifications/    # email/SMS reminders via Celery
```

### Layer responsibilities

| File | Responsibility | What does NOT belong here |
|------|---------------|--------------------------|
| `models.py` | Data shape, constraints, relationships | Business logic, external calls |
| `serializers.py` | Input validation, data transformation | Business decisions, DB queries beyond simple lookups |
| `views.py` | HTTP contract: receive request, call service, return response | Business logic, direct model manipulation |
| `services.py` | Business logic, domain rules, orchestration | HTTP concerns, serializer internals |
| `tasks.py` | Celery async tasks, deferred side effects | Inline business logic (call services instead) |
| `permissions.py` | Custom DRF permission classes | |
| `tests/` | One folder per app, one file per feature area | |

---

## Code standards

- Formatter: **black** (line length 88). No manual formatting.
- Linter: **flake8**. Fix all warnings before considering a task done.
- Types: **mypy** strict on new code. Annotate all function signatures.
- No `fields = '__all__'` in serializers. Ever.
- No raw SQL unless there is a documented reason.
- No `print()` in committed code. Use `logging`.

---

## Rules by layer

### Models

- Fields must have explicit `verbose_name` and `help_text` when the name is not self-evident.
- Always define `__str__`, `class Meta` with `ordering` and `verbose_name`/`verbose_name_plural`.
- Use `get_FOO_display()` for choice fields; define choices as class-level enums or `TextChoices`.
- Avoid business logic in model methods. `clean()` is acceptable for basic field-level invariants.
- Soft deletes: use an `is_active` or `deleted_at` field, never `.delete()` on critical records.

### Serializers

- One serializer per use case when input and output shapes differ (e.g., `AppointmentCreateSerializer`, `AppointmentReadSerializer`).
- Validate field-level rules in `validate_<field>()`, cross-field rules in `validate()`.
- Do not call services or write to the DB inside `validate()`. That belongs in the view or service.
- `create()` and `update()` may call a service but should not contain domain logic themselves.

### Views

- Prefer `ModelViewSet` only when the resource naturally supports full CRUD and the logic is simple.
- Use `APIView` or `GenericAPIView` when actions have non-trivial business rules or do not map cleanly to CRUD.
- Views must not contain business logic. If a view method is growing beyond ~20 lines, move logic to a service.
- Always declare `permission_classes` and `authentication_classes` explicitly — do not rely on global defaults silently.
- Use `@extend_schema` (drf-spectacular) on every endpoint. At minimum: `summary`, `responses`.

### Services

- Services are plain Python functions or classes in `services.py`. No Django view or DRF imports.
- Raise domain-level exceptions (defined in `core/exceptions.py`) instead of HTTP exceptions.
- Services own transactions: wrap multi-step DB operations in `transaction.atomic()`.
- A service function should do one thing. If it is doing three things, split it.

### Tasks (Celery)

- Tasks must be idempotent where possible.
- Do not put business logic inside the task body. Call a service function.
- Always set `bind=True` and handle retries explicitly with `self.retry(exc=..., countdown=...)`.
- Log task start, completion, and failures.

---

## Tests

### Structure

```
appointments/
  tests/
    __init__.py
    factories.py          # AppointmentFactory, etc.
    test_models.py
    test_serializers.py
    test_views.py         # integration: HTTP request → response
    test_services.py      # unit: service logic in isolation
```

### Rules

- Use factories (factory_boy) for all test data. No hardcoded PKs or magic strings.
- Every test file must cover: happy path, validation errors, and the most important failure case.
- View tests use `APIClient` and assert both status code and response body shape.
- Service tests call the service directly, not through HTTP.
- Do not mock the database in tests. Use the real test DB (`pytest-django` manages it).
- Use `@pytest.mark.django_db` on tests that hit the DB. Do not apply it globally.
- Factories go in the app's own `tests/factories.py`. Import across apps only when necessary.

---

## Migrations

- One migration per coherent change (do not bundle unrelated model changes).
- Never edit an existing migration. Always create a new one.
- Data migrations must be separate from schema migrations.
- Every `RunPython` must have a reverse function (even if it is `migrations.RunPython.noop`).
- Before applying a migration to staging/production, check: does it lock a large table? is it reversible?
- Generated migration filenames are fine; only rename them if the default name is truly ambiguous.

---

## API documentation (Swagger / OpenAPI)

- Use `drf-spectacular`. Configure `SPECTACULAR_SETTINGS` in `settings.py`.
- Every viewset action and API view must have `@extend_schema`:
  - `summary`: one line describing what the endpoint does
  - `responses`: explicit response serializer or status code map
  - `request`: explicit request serializer when it differs from the default
- Do not document internal or admin-only endpoints in the public schema. Use `@extend_schema(exclude=True)`.
- Keep the schema consistent: if a field is nullable in the model, mark it as such in the serializer.

---

## Before marking a task as done

1. `poetry run black .` — no diffs
2. `poetry run flake8 .` — no errors
3. `poetry run mypy .` — no new errors on touched files
4. `poetry run pytest -x` — all tests pass
5. New code has at least one test covering the happy path
6. Any new endpoint has `@extend_schema` with `summary` and `responses`
7. No migration was edited, only new ones created

---

## What to avoid

- Business logic in views or serializers
- `fields = '__all__'` in any serializer
- Editing existing migrations
- Importing models from another app's internals (use services or signals to communicate across domains)
- Adding new dependencies to `pyproject.toml` without flagging it first
- Changing Docker configuration or environment variables without explicit instruction
- Large refactors bundled with feature work — keep changes focused and reviewable
- Commenting out code instead of deleting it
- Silencing mypy or flake8 with inline ignores without a written reason in the same line
