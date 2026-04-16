import pytest

from dentora.core.exceptions import ConflictError, NotFoundError
from dentora.patients import services
from dentora.patients.models import Patient
from dentora.patients.tests.factories import InactivePatientFactory, PatientFactory


@pytest.mark.django_db
class TestListPatients:
    def test_returns_active_patients_by_default(self) -> None:
        PatientFactory.create_batch(3)
        InactivePatientFactory()
        qs = services.list_patients()
        assert qs.count() == 3
        assert all(p.is_active for p in qs)

    def test_include_inactive_returns_all(self) -> None:
        PatientFactory.create_batch(2)
        InactivePatientFactory.create_batch(2)
        qs = services.list_patients(include_inactive=True)
        assert qs.count() == 4

    def test_search_by_last_name(self) -> None:
        PatientFactory(last_name="Gomez")
        PatientFactory(last_name="Torres")
        qs = services.list_patients(search="Gom")
        assert qs.count() == 1
        assert qs.first().last_name == "Gomez"  # type: ignore[union-attr]

    def test_search_by_dni(self) -> None:
        PatientFactory(dni="12345678")
        PatientFactory(dni="87654321")
        qs = services.list_patients(search="12345")
        assert qs.count() == 1

    def test_empty_search_returns_all_active(self) -> None:
        PatientFactory.create_batch(5)
        qs = services.list_patients(search="")
        assert qs.count() == 5


@pytest.mark.django_db
class TestGetPatient:
    def test_returns_existing_patient(self) -> None:
        patient = PatientFactory()
        found = services.get_patient(patient.pk)
        assert found.pk == patient.pk

    def test_raises_not_found_for_missing_id(self) -> None:
        import uuid

        with pytest.raises(NotFoundError):
            services.get_patient(uuid.uuid4())


@pytest.mark.django_db
class TestCreatePatient:
    def test_creates_patient_successfully(self) -> None:
        patient = services.create_patient(
            first_name="Ana",
            last_name="Gomez",
            dni="12345678",
            date_of_birth="1990-05-15",
            email="ana@example.com",
        )
        assert patient.pk is not None
        assert patient.first_name == "Ana"
        assert Patient.objects.filter(pk=patient.pk).exists()

    def test_duplicate_dni_raises_conflict(self) -> None:
        PatientFactory(dni="12345678")
        with pytest.raises(ConflictError):
            services.create_patient(
                first_name="Pedro",
                last_name="Lopez",
                dni="12345678",
                date_of_birth="1985-01-01",
            )

    def test_patient_is_active_by_default(self) -> None:
        patient = services.create_patient(
            first_name="Ana",
            last_name="Gomez",
            dni="99000001",
            date_of_birth="1990-05-15",
        )
        assert patient.is_active is True


@pytest.mark.django_db
class TestUpdatePatient:
    def test_updates_allowed_fields(self) -> None:
        patient = PatientFactory(phone="0000000000")
        updated = services.update_patient(
            patient, phone="1122334455", email="new@example.com"
        )
        assert updated.phone == "1122334455"
        assert updated.email == "new@example.com"

    def test_dni_is_not_updatable(self) -> None:
        original_dni = "12345678"
        patient = PatientFactory(dni=original_dni)
        services.update_patient(patient, dni="99999999")
        patient.refresh_from_db()
        assert patient.dni == original_dni

    def test_no_fields_does_not_raise(self) -> None:
        patient = PatientFactory()
        result = services.update_patient(patient)
        assert result.pk == patient.pk


@pytest.mark.django_db
class TestDeactivatePatient:
    def test_sets_is_active_false(self) -> None:
        patient = PatientFactory()
        deactivated = services.deactivate_patient(patient.pk)
        assert deactivated.is_active is False
        patient.refresh_from_db()
        assert patient.is_active is False

    def test_raises_not_found_for_missing_id(self) -> None:
        import uuid

        with pytest.raises(NotFoundError):
            services.deactivate_patient(uuid.uuid4())
