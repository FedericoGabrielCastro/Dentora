# create-drf-endpoint

Implement a REST endpoint in Dentora across all required layers: serializer, view, URL, and OpenAPI docs.

**Usage:** `/create-drf-endpoint <app>/<action> [brief description]`

**Examples:**
- `/create-drf-endpoint appointments/book create a new appointment for a patient with a dentist`
- `/create-drf-endpoint appointments/cancel cancel an existing appointment and trigger a notification`
- `/create-drf-endpoint appointments/reschedule move an appointment to a new time slot`
- `/create-drf-endpoint appointments/list-by-dentist list all upcoming appointments for a given dentist`
- `/create-drf-endpoint dentists/availability query available slots for a dentist in a date range`

---

## What this skill does

You are implementing a new REST endpoint for Dentora, a dental appointment management backend.
Read existing files in the target app before writing: `serializers.py`, `views.py`, `services.py`, `urls.py`, `permissions.py`.
Do not overwrite existing code — add to it.

The argument is: $ARGUMENTS

---

## Step 1 — Choose the right view type

Decide before writing any code:

**Use `ModelViewSet` when:**
- The endpoint is standard CRUD on a single model
- No significant business rules beyond validate + save
- Example: managing `Treatment` records linked to an appointment

**Use `APIView` or a `GenericAPIView` mixin when:**
- The action has domain logic (availability checks, conflict detection, state transitions)
- The action spans multiple models
- The URL does not map to a single resource (e.g., `/appointments/{id}/cancel`)
- Example: booking, cancelling, rescheduling, querying availability

For Dentora, most appointment-related actions will be `APIView`. State changes (cancel, reschedule, confirm) are never plain PATCH — they are explicit actions with business rules.

Briefly explain your choice in a comment at the top of the view class.

---

## Step 2 — Serializers (`serializers.py`)

**Rules:**
- Never use `fields = '__all__'`. List every field explicitly.
- If the request shape differs from the response shape, create two serializers:
  - `<Action>InputSerializer` — validates the incoming payload
  - `<Action>OutputSerializer` — shapes the response
- Validate field-level rules in `validate_<field>()`.
- Validate cross-field rules in `validate()`.
- Do not call services or write to the DB inside serializers.
- Do not raise `Http404` or `PermissionDenied` from serializers — only `serializers.ValidationError`.

**Patterns by use case:**

| Action | Serializer approach |
|--------|-------------------|
| Book appointment | `AppointmentBookInputSerializer` (patient, dentist, slot) + `AppointmentReadSerializer` (full output) |
| Cancel appointment | `AppointmentCancelInputSerializer` (reason optional) + simple status response |
| Reschedule | `AppointmentRescheduleInputSerializer` (new slot) + `AppointmentReadSerializer` |
| List by dentist | No input serializer needed; `AppointmentReadSerializer` for output |
| Query availability | `AvailabilityQueryInputSerializer` (dentist_id, date_from, date_to) + `AvailabilitySlotSerializer` |

---

## Step 3 — Service layer (`services.py`)

The view must not contain business logic. For every action, create or update a service function:

```python
# Good
def book_appointment(patient_id: int, dentist_id: int, slot_id: int) -> Appointment:
    ...

# Bad — HTTP concerns in a service
def book_appointment(request, serializer):
    ...
```

**Rules:**
- Service functions receive plain Python types or model instances, never `request` objects.
- Wrap multi-step writes in `transaction.atomic()`.
- Raise exceptions from `core/exceptions.py` for domain errors (create the file if it does not exist).
- Side effects (notifications, Celery tasks) are triggered from the service after the transaction commits, using `transaction.on_commit(lambda: ...)`.

**Core domain rules to encode in services:**
- A patient cannot have two confirmed appointments at the same time.
- A dentist cannot be booked outside their availability slots.
- Cancellation is only allowed before a configurable cutoff window.
- Rescheduling creates a new slot check, does not blindly PATCH the time.
- Availability slots belong to a dentist + clinic combination.

---

## Step 4 — View (`views.py`)

Structure every view the same way:

```python
class AppointmentBookView(APIView):
    # Reason for APIView: booking involves availability check and conflict detection.

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]  # or SessionAuthentication

    @extend_schema(
        summary="Book a new appointment",
        request=AppointmentBookInputSerializer,
        responses={
            201: AppointmentReadSerializer,
            400: OpenApiResponse(description="Validation error or slot unavailable"),
            409: OpenApiResponse(description="Conflicting appointment exists"),
        },
        tags=["appointments"],
    )
    def post(self, request):
        serializer = AppointmentBookInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        appointment = book_appointment(**serializer.validated_data)

        return Response(
            AppointmentReadSerializer(appointment).data,
            status=status.HTTP_201_CREATED,
        )
```

**Rules:**
- `permission_classes` and `authentication_classes` must be declared explicitly on every view.
- The view body for each method should not exceed ~20 lines. If it does, move logic to the service.
- Return appropriate HTTP status codes: `200` for reads, `201` for creates, `204` for deletes/state changes with no body, `400` for validation errors, `409` for conflicts.
- Catch domain exceptions from `core/exceptions.py` and convert them to HTTP responses in the view or via a global exception handler in `core/`.

---

## Step 5 — URL registration (`urls.py`)

For `APIView`:
```python
path("appointments/book/", AppointmentBookView.as_view(), name="appointment-book"),
path("appointments/<int:pk>/cancel/", AppointmentCancelView.as_view(), name="appointment-cancel"),
path("appointments/<int:pk>/reschedule/", AppointmentRescheduleView.as_view(), name="appointment-reschedule"),
```

For `ModelViewSet`:
```python
router = DefaultRouter()
router.register("treatments", TreatmentViewSet, basename="treatment")
```

Use kebab-case URL paths. Use `<int:pk>` for resource identifiers. Do not use query params for resource identity.

---

## Step 6 — OpenAPI documentation

Every view must have `@extend_schema`. Minimum required:

```python
@extend_schema(
    summary="One sentence. What does this endpoint do?",
    request=InputSerializer,           # omit for GET
    responses={
        200: OutputSerializer,
        400: OpenApiResponse(description="Validation errors"),
    },
    tags=["appointments"],             # group by domain
)
```

Add `description` for non-obvious endpoints. Include example payloads via `OpenApiExample` when the shape is complex.

Do not document internal or staff-only endpoints in the public schema — use `@extend_schema(exclude=True)`.

---

## Step 7 — Tests

Create or update `tests/test_views.py` in the target app. Write at minimum:

**For every endpoint:**
1. Happy path — correct input returns the expected status and response shape
2. Validation error — invalid input returns `400` with error detail
3. Permission check — unauthenticated request returns `401`

**For state-changing endpoints (cancel, reschedule, book):**
4. Business rule violation — e.g., booking a slot that is already taken returns `409`
5. Not found — resource does not exist returns `404`

Use `APIClient` and `factory_boy` factories. Do not hardcode PKs or user IDs.

```python
@pytest.mark.django_db
class TestAppointmentBookView:
    def test_book_appointment_success(self, api_client, patient, dentist, available_slot):
        ...

    def test_book_appointment_slot_unavailable(self, api_client, patient, dentist, booked_slot):
        ...

    def test_book_appointment_unauthenticated(self, api_client):
        response = api_client.post("/api/appointments/book/", {})
        assert response.status_code == 401
```

---

## Validation checklist

Before marking the endpoint as done:

- [ ] View type choice is justified with a comment
- [ ] No `fields = '__all__'` in serializers
- [ ] Input and output serializers are separate if shapes differ
- [ ] No business logic in view or serializer
- [ ] Service wraps multi-step writes in `transaction.atomic()`
- [ ] Side effects use `transaction.on_commit()`
- [ ] `permission_classes` declared explicitly on the view
- [ ] `@extend_schema` present with `summary`, `request`, `responses`, and `tags`
- [ ] URL registered with a `name`
- [ ] At least 3 tests: happy path, validation error, unauthenticated
- [ ] Correct HTTP status codes used throughout

---

## Anti-patterns to avoid

| Anti-pattern | Problem | Fix |
|---|---|---|
| Business logic in the view | Hard to test, can't reuse | Move to `services.py` |
| `serializer.save()` with ORM logic | Bypasses service layer | Call service from the view, not serializer |
| `queryset.update()` for state changes | Skips signals, `save()`, and business rules | Use a service that loads, validates, and saves the instance |
| Missing `permission_classes` | Falls back to global default silently | Always declare explicitly |
| Plain `PATCH` for state transitions (cancel, confirm) | State machines need explicit actions | Use dedicated endpoints: `/cancel/`, `/confirm/` |
| `raise Http404` inside a service | Mixes HTTP and domain logic | Raise `AppointmentNotFound` from `core/exceptions.py`; catch in view |
| No `tags` in `@extend_schema` | Swagger shows one flat list of 40 endpoints | Group by domain: `appointments`, `patients`, `dentists` |
| Test that only checks status code | Doesn't verify the response body is correct | Assert `response.data` fields too |
