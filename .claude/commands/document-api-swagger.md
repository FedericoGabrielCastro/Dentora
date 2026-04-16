# document-api-swagger

Document a Dentora endpoint in Swagger. Read the code first — document what it actually does, not what it should do.

**Usage:** `/document-api-swagger <app>/<view or endpoint name>`

**Examples:**
- `/document-api-swagger appointments/AppointmentBookView`
- `/document-api-swagger appointments/AppointmentCancelView`
- `/document-api-swagger dentists/AvailabilityView`
- `/document-api-swagger patients/PatientViewSet`
- `/document-api-swagger appointments/AppointmentViewSet.list`

---

## What this skill does

You are documenting a DRF endpoint for Dentora using the Swagger library already present in the project.
Read the view, serializer(s), and URL configuration before writing a single annotation.
Do not document from assumption — document from code.

The argument is: $ARGUMENTS

---

## Step 1 — Read before documenting

Before adding any `@extend_schema`, read and note:

1. **`views.py`** — What HTTP methods does this view expose? What serializer does it use for input? For output? What permissions are declared?
2. **`serializers.py`** — What fields are required vs. optional? What `validate_*` methods exist? What choices or constraints apply?
3. **`urls.py`** — What is the full URL path? Are there path parameters (`<int:pk>`)? Are there query parameters (check `get_queryset` or `filter_backends`)?
4. **`services.py`** (if applicable) — What domain errors can the service raise? These map to error responses.
5. **`permissions.py`** — What permission classes are used? This determines authentication requirements.

Write down what you found before touching the code. If the implementation has a bug or inconsistency (e.g., the view returns 200 but should return 201), flag it before documenting it — document the intended behavior and note the discrepancy.

---

## Step 2 — Detect the Swagger library in use

Check which library is installed:

```bash
# Check pyproject.toml or requirements
grep -E "drf-spectacular|drf-yasg|rest_framework" pyproject.toml
```

- **drf-spectacular** (preferred): use `@extend_schema`, `OpenApiResponse`, `OpenApiExample`, `OpenApiParameter`
- **drf-yasg**: use `@swagger_auto_schema`

If neither is installed, stop and flag it — do not introduce a new library without checking first.
For the rest of this skill, drf-spectacular syntax is used. Adjust if the project uses drf-yasg.

---

## Step 3 — Identify inputs

Document every input the endpoint accepts:

### Request body (POST, PUT, PATCH)
```python
request=AppointmentBookInputSerializer
```
Read the serializer field by field. Note for each:
- Required or optional?
- Type (int, str, date, datetime, choice)?
- Any format constraint (e.g., `YYYY-MM-DD`, UUID)?
- Any cross-field dependency?

### Path parameters
```python
# Automatically inferred by drf-spectacular for <int:pk>
# Document explicitly when the param has non-obvious semantics
parameters=[
    OpenApiParameter(
        name="pk",
        location=OpenApiParameter.PATH,
        description="Appointment ID",
        required=True,
        type=int,
    )
]
```

### Query parameters
```python
# Document every query param used in get_queryset(), filter_backends, or manual request.query_params
parameters=[
    OpenApiParameter(
        name="dentist_id",
        location=OpenApiParameter.QUERY,
        description="Filter appointments by dentist",
        required=False,
        type=int,
    ),
    OpenApiParameter(
        name="date_from",
        location=OpenApiParameter.QUERY,
        description="Start of date range (YYYY-MM-DD)",
        required=False,
        type=str,
    ),
]
```

### Headers
Only document headers that the view explicitly reads (e.g., `Accept-Language`, `X-Clinic-ID`). Do not document `Authorization` — drf-spectacular infers it from `permission_classes`.

---

## Step 4 — Identify responses

Map every HTTP status code the view can return. Do not invent codes — read the view and service.

### Standard mapping for Dentora endpoints

| Situation | Status | Body |
|-----------|--------|------|
| Resource created | `201` | Output serializer |
| Action completed (with body) | `200` | Output serializer |
| Action completed (no body) | `204` | Empty |
| Validation error | `400` | `{"field": ["error message"]}` |
| Unauthenticated | `401` | `{"detail": "..."}` |
| Forbidden (authenticated but no permission) | `403` | `{"detail": "..."}` |
| Resource not found | `404` | `{"detail": "Not found."}` |
| Business rule conflict | `409` | `{"detail": "..."}` |

```python
responses={
    201: AppointmentReadSerializer,
    400: OpenApiResponse(description="Validation error. Returns field-level error messages."),
    401: OpenApiResponse(description="Authentication credentials were not provided."),
    404: OpenApiResponse(description="Appointment not found."),
    409: OpenApiResponse(description="Slot is already booked or patient has a conflicting appointment."),
}
```

For `204 No Content`:
```python
responses={
    204: OpenApiResponse(description="Appointment cancelled successfully."),
    404: OpenApiResponse(description="Appointment not found."),
}
```

---

## Step 5 — Write the annotation

Apply `@extend_schema` with all the information gathered.

### APIView (method-level decoration)

```python
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample, OpenApiParameter


class AppointmentBookView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Book a new appointment",
        description=(
            "Creates a new appointment between a patient and a dentist for an available slot. "
            "Validates that the slot is not already taken and that the patient has no conflicting appointment."
        ),
        request=AppointmentBookInputSerializer,
        responses={
            201: AppointmentReadSerializer,
            400: OpenApiResponse(
                description="Validation error. Returned when required fields are missing or invalid."
            ),
            401: OpenApiResponse(description="Authentication credentials were not provided."),
            409: OpenApiResponse(
                description="Conflict. The slot is already booked or the patient has an overlapping appointment."
            ),
        },
        examples=[
            OpenApiExample(
                name="Successful booking",
                request_only=True,
                value={
                    "patient_id": 12,
                    "dentist_id": 3,
                    "slot_id": 47,
                },
            ),
            OpenApiExample(
                name="Booking confirmed",
                response_only=True,
                status_codes=["201"],
                value={
                    "id": 89,
                    "status": "scheduled",
                    "patient": {"id": 12, "full_name": "Ana Gómez"},
                    "dentist": {"id": 3, "full_name": "Dr. Martín López"},
                    "scheduled_at": "2026-04-20T10:30:00-03:00",
                    "created_at": "2026-04-16T09:00:00-03:00",
                },
            ),
        ],
        tags=["appointments"],
    )
    def post(self, request):
        ...
```

### ModelViewSet (action-level decoration)

```python
from drf_spectacular.utils import extend_schema, extend_schema_view


@extend_schema_view(
    list=extend_schema(
        summary="List appointments",
        description="Returns a paginated list of appointments. Filter by dentist_id, patient_id, or date range.",
        parameters=[
            OpenApiParameter("dentist_id", int, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("date_from", str, OpenApiParameter.QUERY, required=False, description="YYYY-MM-DD"),
            OpenApiParameter("date_to", str, OpenApiParameter.QUERY, required=False, description="YYYY-MM-DD"),
        ],
        tags=["appointments"],
    ),
    retrieve=extend_schema(
        summary="Retrieve an appointment",
        tags=["appointments"],
    ),
    create=extend_schema(
        summary="Create an appointment",
        tags=["appointments"],
    ),
    update=extend_schema(exclude=True),     # not exposed
    partial_update=extend_schema(exclude=True),
    destroy=extend_schema(
        summary="Delete an appointment",
        tags=["appointments"],
    ),
)
class AppointmentViewSet(ModelViewSet):
    ...
```

---

## Step 6 — Examples

Examples are worth more than long descriptions. Write at least one request and one response example per non-trivial endpoint.

**Rules for examples:**
- Use realistic Argentine names, DNI numbers, and timezones (`America/Argentina/Buenos_Aires`, UTC-3).
- Use plausible appointment dates (not `2000-01-01` or `9999-12-31`).
- Reflect the actual field names from the serializer — not what you think they should be.
- For error examples, show the actual DRF error structure: `{"field": ["message"]}`.

**Domain examples for Dentora:**

```python
# Patient
{"id": 7, "full_name": "Laura Pereyra", "dni": "28451203", "phone": "+5491150001234"}

# Dentist
{"id": 2, "full_name": "Dr. Carlos Méndez", "specialization": "orthodontics", "license_number": "MP-00342"}

# Appointment
{
    "id": 15,
    "status": "scheduled",
    "patient": {"id": 7, "full_name": "Laura Pereyra"},
    "dentist": {"id": 2, "full_name": "Dr. Carlos Méndez"},
    "scheduled_at": "2026-04-22T14:00:00-03:00",
    "treatment": "cleaning",
}

# Availability slot
{"id": 31, "dentist_id": 2, "starts_at": "2026-04-22T14:00:00-03:00", "ends_at": "2026-04-22T14:30:00-03:00", "is_available": true}

# Validation error
{"slot_id": ["This slot is no longer available."]}

# Conflict error
{"detail": "The patient already has a confirmed appointment at this time."}
```

---

## Step 7 — Verify alignment

After adding the annotation, re-read the view and serializer against the documentation you wrote:

- [ ] Every documented field in `request` exists in the input serializer
- [ ] Every documented field in `responses[200/201]` exists in the output serializer
- [ ] Required fields in the serializer are not documented as optional
- [ ] All `validate_*` methods and cross-field rules are reflected in error descriptions
- [ ] Status codes in the annotation match what the view actually returns
- [ ] Tags group this endpoint correctly with related endpoints
- [ ] Examples use real field names, not assumed ones
- [ ] Endpoints with no body use `204` and `OpenApiResponse(description="...")`, not a serializer

If you find a mismatch between documentation and code, call it out explicitly:
```
⚠ Discrepancy: the view returns `status.HTTP_200_OK` but the operation creates a resource.
  This should be 201. Flagging for correction — documenting as 201 (intended behavior).
```

---

## Validation checklist

- [ ] View, serializer(s), and URL read before writing any annotation
- [ ] `summary` is one clear sentence (no "this endpoint...")
- [ ] `description` explains non-obvious behavior, constraints, or business rules
- [ ] `request` reflects the actual input serializer
- [ ] All documented request fields match the serializer (no invented fields)
- [ ] `responses` covers success and all relevant error codes
- [ ] `204` responses use `OpenApiResponse(description=...)`, not a serializer
- [ ] `parameters` documents all path params, query params, and custom headers
- [ ] At least one `OpenApiExample` for non-trivial endpoints
- [ ] Examples use Dentora-domain data (Argentine names, real appointment context)
- [ ] `tags` assigned (one tag per domain app: `appointments`, `patients`, `dentists`, etc.)
- [ ] `exclude=True` applied to any action not meant for public consumption
- [ ] Documented status codes match what the view code actually returns
- [ ] No fields documented that do not exist in the serializer or response

---

## What not to do

- Do not copy the serializer field list and paste it as a description — explain behavior, not structure
- Do not document error codes the endpoint cannot return (e.g., `409` on a read-only endpoint)
- Do not write `description="string"` for a field named `status` with defined choices — list the choices
- Do not leave `summary` empty or set it to the view class name
- Do not add `@extend_schema` to internal views, admin views, or health-check endpoints — use `exclude=True`
- Do not duplicate documentation that drf-spectacular already infers correctly from the serializer
