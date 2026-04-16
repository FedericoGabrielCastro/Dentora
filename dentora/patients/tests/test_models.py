import pytest

from dentora.patients.models import Patient
from dentora.patients.tests.factories import PatientFactory


@pytest.mark.django_db
class TestPatientModel:
    def test_str_representation(self) -> None:
        patient = PatientFactory(
            first_name="Ana",
            last_name="Gomez",
            dni="12345678",
        )
        assert str(patient) == "Gomez, Ana (DNI: 12345678)"

    def test_get_full_name(self) -> None:
        patient = PatientFactory(first_name="Ana", last_name="Gomez")
        assert patient.get_full_name() == "Ana Gomez"

    def test_dni_is_unique(self) -> None:
        PatientFactory(dni="99999999")
        with pytest.raises(Exception):
            PatientFactory(dni="99999999")

    def test_is_active_defaults_to_true(self) -> None:
        patient = PatientFactory()
        assert patient.is_active is True

    def test_ordering_by_last_name_first_name(self) -> None:
        PatientFactory(first_name="Zara", last_name="Alvarez")
        PatientFactory(first_name="Ana", last_name="Alvarez")
        PatientFactory(first_name="Carlos", last_name="Benitez")

        names = list(Patient.objects.values_list("first_name", flat=True))
        assert names.index("Ana") < names.index("Zara")
        assert names.index("Zara") < names.index("Carlos")

    def test_created_at_is_set_on_creation(self) -> None:
        patient = PatientFactory()
        assert patient.created_at is not None

    def test_optional_fields_allow_blank(self) -> None:
        patient = PatientFactory(email="", phone="", address="", notes="")
        assert patient.email == ""
        assert patient.phone == ""
        assert patient.address == ""
        assert patient.notes == ""
