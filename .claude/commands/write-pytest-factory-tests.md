# write-pytest-factory-tests

Write robust pytest tests for Dentora using factory_boy. Covers models, serializers, services, DRF endpoints, and Celery tasks.

**Usage:** `/write-pytest-factory-tests <app>/<target> [what to test]`

**Examples:**
- `/write-pytest-factory-tests appointments/services test book_appointment with conflict detection`
- `/write-pytest-factory-tests appointments/views test AppointmentBookView happy path and auth`
- `/write-pytest-factory-tests appointments/serializers test AppointmentBookInputSerializer validation`
- `/write-pytest-factory-tests appointments/models test Appointment constraints and __str__`
- `/write-pytest-factory-tests notifications/tasks test send_appointment_reminder retries on failure`

---

## What this skill does

You are writing tests for the Dentora backend. Before writing anything:
1. Read the file being tested.
2. Read `tests/factories.py` in the same app (if it exists) — reuse existing factories, don't duplicate them.
3. Read `conftest.py` at the app and project level (if they exist) — reuse fixtures.

The argument is: $ARGUMENTS

---

## Factories (`tests/factories.py`)

Factories are the foundation. Write them before the tests.

**Rules:**
- One factory per model. Place all factories for an app in `tests/factories.py`.
- Use `factory.SubFactory` for FK relationships — never hardcode PKs.
- Use `factory.LazyAttribute` for fields derived from other fields (e.g., email from name).
- Use `factory.Faker` for realistic data. Prefer it over static strings.
- Use `factory.Trait` for common variants (e.g., a cancelled appointment, an inactive patient).
- Never call `.save()` manually inside a factory.

**Base pattern:**
```python
import factory
from factory.django import DjangoModelFactory
from faker import Faker

fake = Faker("es_AR")  # Argentine locale for names, phones, DNI


class ClinicFactory(DjangoModelFactory):
    class Meta:
        model = "clinics.Clinic"

    name = factory.Faker("company")
    address = factory.Faker("address")
    phone = factory.Faker("phone_number")
    is_active = True


class DentistFactory(DjangoModelFactory):
    class Meta:
        model = "dentists.Dentist"

    user = factory.SubFactory(UserFactory)
    license_number = factory.Sequence(lambda n: f"MP-{n:05d}")
    specialization = Dentist.Specialization.GENERAL
    is_active = True


class PatientFactory(DjangoModelFactory):
    class Meta:
        model = "patients.Patient"

    user = factory.SubFactory(UserFactory)
    dni = factory.Sequence(lambda n: f"{20_000_000 + n}")
    phone = factory.Faker("phone_number")
    is_active = True


class AppointmentFactory(DjangoModelFactory):
    class Meta:
        model = "appointments.Appointment"

    patient = factory.SubFactory(PatientFactory)
    dentist = factory.SubFactory(DentistFactory)
    scheduled_at = factory.LazyFunction(
        lambda: timezone.now() + timedelta(days=3)
    )
    status = Appointment.Status.SCHEDULED
    is_active = True

    class Params:
        cancelled = factory.Trait(status=Appointment.Status.CANCELLED)
        confirmed = factory.Trait(status=Appointment.Status.CONFIRMED)
        in_the_past = factory.Trait(
            scheduled_at=factory.LazyFunction(
                lambda: timezone.now() - timedelta(days=1)
            )
        )
```

**Traits in practice:**
```python
AppointmentFactory()                        # scheduled, future
AppointmentFactory(cancelled=True)          # cancelled
AppointmentFactory(confirmed=True)          # confirmed
AppointmentFactory(in_the_past=True)        # yesterday
AppointmentFactory.build()                  # no DB write, for unit tests
```

---

## Test structure by layer

### Models

Test what cannot be caught by reading the code: constraints, `__str__`, default values, and `clean()` validations.

```
tests/test_models.py
```

```python
@pytest.mark.django_db
class TestAppointmentModel:
    def test_str_includes_patient_dentist_and_date(self):
        appointment = AppointmentFactory()
        assert str(appointment.patient) in str(appointment)
        assert str(appointment.dentist) in str(appointment)

    def test_default_status_is_scheduled(self):
        appointment = AppointmentFactory()
        assert appointment.status == Appointment.Status.SCHEDULED

    def test_unique_constraint_prevents_duplicate_confirmed_slot(self):
        slot = AvailabilitySlotFactory()
        AppointmentFactory(slot=slot, status=Appointment.Status.CONFIRMED)
        with pytest.raises(IntegrityError):
            AppointmentFactory(slot=slot, status=Appointment.Status.CONFIRMED)

    def test_created_at_is_set_automatically(self):
        appointment = AppointmentFactory()
        assert appointment.created_at is not None
```

Only test constraints if they are defined in `Meta.constraints` or `clean()`. Do not write tests that just verify Django field definitions.

---

### Serializers

Test validation logic. Do not test that DRF does its job — test your `validate_<field>()` and `validate()` methods.

```
tests/test_serializers.py
```

```python
class TestAppointmentBookInputSerializer:
    def test_valid_data_passes(self, patient, dentist, available_slot):
        data = {
            "patient_id": patient.pk,
            "dentist_id": dentist.pk,
            "slot_id": available_slot.pk,
        }
        serializer = AppointmentBookInputSerializer(data=data)
        assert serializer.is_valid()

    def test_past_slot_is_rejected(self, patient, dentist, past_slot):
        data = {
            "patient_id": patient.pk,
            "dentist_id": dentist.pk,
            "slot_id": past_slot.pk,
        }
        serializer = AppointmentBookInputSerializer(data=data)
        assert not serializer.is_valid()
        assert "slot_id" in serializer.errors

    def test_missing_required_field_returns_error(self, patient, dentist):
        data = {"patient_id": patient.pk}  # missing dentist_id and slot_id
        serializer = AppointmentBookInputSerializer(data=data)
        assert not serializer.is_valid()
        assert "dentist_id" in serializer.errors
        assert "slot_id" in serializer.errors
```

Serializer tests do not need `@pytest.mark.django_db` unless the `validate()` method queries the DB.

---

### Services

Unit-test the business logic in isolation. This is the most important test layer.

```
tests/test_services.py
```

**Cover for every service function:**
1. Happy path — expected inputs produce expected output and DB state.
2. Each business rule violation — one test per rule.
3. Atomicity — if the service fails mid-way, no partial writes persist.

```python
@pytest.mark.django_db
class TestBookAppointment:
    def test_creates_appointment_with_correct_status(self, patient, dentist, available_slot):
        appointment = book_appointment(
            patient_id=patient.pk,
            dentist_id=dentist.pk,
            slot_id=available_slot.pk,
        )
        assert appointment.pk is not None
        assert appointment.status == Appointment.Status.SCHEDULED
        assert appointment.patient == patient

    def test_raises_if_slot_already_booked(self, patient, dentist, booked_slot):
        with pytest.raises(SlotUnavailableError):
            book_appointment(
                patient_id=patient.pk,
                dentist_id=dentist.pk,
                slot_id=booked_slot.pk,
            )

    def test_raises_if_patient_has_conflicting_appointment(self, patient, dentist, available_slot):
        AppointmentFactory(patient=patient, scheduled_at=available_slot.starts_at, confirmed=True)
        with pytest.raises(PatientConflictError):
            book_appointment(
                patient_id=patient.pk,
                dentist_id=dentist.pk,
                slot_id=available_slot.pk,
            )

    def test_rolls_back_on_notification_failure(self, patient, dentist, available_slot, mocker):
        mocker.patch("appointments.services.queue_booking_notification", side_effect=Exception)
        with pytest.raises(Exception):
            book_appointment(...)
        assert not Appointment.objects.filter(patient=patient, slot=available_slot).exists()
```

---

### DRF Views (integration tests)

Test the full HTTP contract: status code, response body shape, and side effects.

```
tests/test_views.py
```

```python
@pytest.fixture
def auth_client(api_client, patient_user):
    api_client.force_authenticate(user=patient_user)
    return api_client


@pytest.mark.django_db
class TestAppointmentBookView:
    url = "/api/appointments/book/"

    def test_returns_201_with_appointment_data(self, auth_client, patient, dentist, available_slot):
        payload = {
            "patient_id": patient.pk,
            "dentist_id": dentist.pk,
            "slot_id": available_slot.pk,
        }
        response = auth_client.post(self.url, payload)
        assert response.status_code == 201
        assert response.data["status"] == "scheduled"
        assert response.data["patient"]["id"] == patient.pk

    def test_returns_400_on_invalid_payload(self, auth_client):
        response = auth_client.post(self.url, {})
        assert response.status_code == 400
        assert "patient_id" in response.data

    def test_returns_401_for_unauthenticated_request(self, api_client):
        response = api_client.post(self.url, {})
        assert response.status_code == 401

    def test_returns_409_when_slot_is_already_booked(self, auth_client, patient, dentist, booked_slot):
        payload = {"patient_id": patient.pk, "dentist_id": dentist.pk, "slot_id": booked_slot.pk}
        response = auth_client.post(self.url, payload)
        assert response.status_code == 409

    def test_returns_404_when_dentist_does_not_exist(self, auth_client, patient, available_slot):
        payload = {"patient_id": patient.pk, "dentist_id": 99999, "slot_id": available_slot.pk}
        response = auth_client.post(self.url, payload)
        assert response.status_code == 404
```

**Shared fixtures in `conftest.py`:**
```python
# conftest.py
import pytest
from rest_framework.test import APIClient

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def patient(db):
    return PatientFactory()

@pytest.fixture
def dentist(db):
    return DentistFactory()

@pytest.fixture
def available_slot(db, dentist):
    return AvailabilitySlotFactory(dentist=dentist)

@pytest.fixture
def booked_slot(db, dentist):
    slot = AvailabilitySlotFactory(dentist=dentist)
    AppointmentFactory(slot=slot, confirmed=True)
    return slot
```

---

### Celery tasks

Test task logic, not Celery internals. Call the task function directly — do not use `.delay()` in tests.

```
tests/test_tasks.py
```

```python
@pytest.mark.django_db
class TestSendAppointmentReminder:
    def test_sends_email_for_upcoming_appointment(self, appointment, mocker):
        mock_send = mocker.patch("notifications.tasks.send_reminder_email")
        send_appointment_reminder(appointment_id=appointment.pk)
        mock_send.assert_called_once_with(appointment)

    def test_does_nothing_for_cancelled_appointment(self, mocker):
        appointment = AppointmentFactory(cancelled=True)
        mock_send = mocker.patch("notifications.tasks.send_reminder_email")
        send_appointment_reminder(appointment_id=appointment.pk)
        mock_send.assert_not_called()

    def test_retries_on_transient_email_failure(self, appointment, mocker):
        mocker.patch(
            "notifications.tasks.send_reminder_email",
            side_effect=ConnectionError("SMTP timeout"),
        )
        task = send_appointment_reminder.s(appointment_id=appointment.pk)
        with pytest.raises(Retry):
            task.apply()
```

---

## `conftest.py` conventions

- Project-level `conftest.py` (`dentora/conftest.py`): `api_client`, `user`, `admin_user`.
- App-level `conftest.py` (`appointments/tests/conftest.py`): app-specific fixtures like `patient`, `dentist`, `available_slot`, `booked_slot`.
- Never duplicate a fixture across conftest files. If it is shared, promote it to the parent level.

---

## Validation checklist

Before marking tests as done:

- [ ] All factories use `SubFactory` for FK — no hardcoded PKs
- [ ] Existing factories in `tests/factories.py` were reused, not duplicated
- [ ] Shared fixtures are in `conftest.py`, not copy-pasted across test files
- [ ] Every service test covers: happy path, each business rule violation, and atomicity
- [ ] Every view test covers: happy path, validation error, unauthenticated request
- [ ] State-change view tests also cover: conflict/409, not found/404
- [ ] Celery task tests call the function directly — no `.delay()` in tests
- [ ] No `@pytest.mark.django_db` on tests that do not hit the DB
- [ ] Test class names start with `Test`, test function names start with `test_` and describe the scenario
- [ ] No `assert response.status_code == 200` as the only assertion in a view test

---

## Anti-patterns to avoid

| Anti-pattern | Problem | Fix |
|---|---|---|
| Hardcoded PKs (`patient_id=1`) | Breaks when DB state changes | Use `patient.pk` from a factory |
| `User.objects.create(username="test")` in every test | Brittle, duplicated, no FK chain | Use `UserFactory` |
| Testing that Django validates `required=True` | Tests the framework, not your code | Only test your custom `validate_*` logic |
| Mocking the DB | Mocks diverge from real behavior; false confidence | Use `pytest-django` with a real test DB |
| `@pytest.mark.django_db` on every class globally | Hides tests that should not need the DB | Apply per-class or per-function |
| One giant test with 10 assertions | Hard to diagnose failures | One test per scenario |
| `response.status_code == 200` as the sole assertion | Does not verify the response body | Also assert key fields in `response.data` |
| Using `.delay()` to test Celery tasks | Tests the broker, not the logic | Call task function directly: `my_task(arg=...)` |
| Factories that `.save()` or call services internally | Side effects in test setup are unpredictable | Factories only create model instances |
| Fixture setup inside the test function body | Clutters the test, hard to reuse | Move shared setup to `conftest.py` fixtures |
