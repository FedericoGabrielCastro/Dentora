import pytest

from dentora.patients.serializers import (
    PatientCreateSerializer,
    PatientReadSerializer,
    PatientUpdateSerializer,
)
from dentora.patients.tests.factories import PatientFactory


@pytest.mark.django_db
class TestPatientReadSerializer:
    def test_output_shape(self) -> None:
        patient = PatientFactory()
        data = PatientReadSerializer(patient).data
        assert set(data.keys()) == {
            "id",
            "first_name",
            "last_name",
            "full_name",
            "dni",
            "email",
            "phone",
            "date_of_birth",
            "address",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        }

    def test_full_name_is_computed(self) -> None:
        patient = PatientFactory(first_name="Ana", last_name="Gomez")
        data = PatientReadSerializer(patient).data
        assert data["full_name"] == "Ana Gomez"


class TestPatientCreateSerializer:
    def test_valid_payload_passes(self) -> None:
        payload = {
            "first_name": "Ana",
            "last_name": "Gomez",
            "dni": "12345678",
            "date_of_birth": "1990-05-15",
            "email": "ana@example.com",
            "phone": "1122334455",
        }
        serializer = PatientCreateSerializer(data=payload)
        assert serializer.is_valid(), serializer.errors

    def test_dni_is_stripped(self) -> None:
        payload = {
            "first_name": "Ana",
            "last_name": "Gomez",
            "dni": "  12345678  ",
            "date_of_birth": "1990-05-15",
        }
        serializer = PatientCreateSerializer(data=payload)
        assert serializer.is_valid()
        assert serializer.validated_data["dni"] == "12345678"

    def test_first_last_name_are_stripped(self) -> None:
        payload = {
            "first_name": "  Ana  ",
            "last_name": "  Gomez  ",
            "dni": "12345678",
            "date_of_birth": "1990-05-15",
        }
        serializer = PatientCreateSerializer(data=payload)
        assert serializer.is_valid()
        assert serializer.validated_data["first_name"] == "Ana"
        assert serializer.validated_data["last_name"] == "Gomez"

    def test_missing_required_fields_fails(self) -> None:
        serializer = PatientCreateSerializer(data={})
        assert not serializer.is_valid()
        assert "first_name" in serializer.errors
        assert "last_name" in serializer.errors
        assert "dni" in serializer.errors
        assert "date_of_birth" in serializer.errors

    def test_optional_fields_have_defaults(self) -> None:
        payload = {
            "first_name": "Ana",
            "last_name": "Gomez",
            "dni": "12345678",
            "date_of_birth": "1990-05-15",
        }
        serializer = PatientCreateSerializer(data=payload)
        assert serializer.is_valid()
        assert serializer.validated_data["email"] == ""
        assert serializer.validated_data["phone"] == ""


class TestPatientUpdateSerializer:
    def test_all_fields_optional(self) -> None:
        serializer = PatientUpdateSerializer(data={})
        assert serializer.is_valid()

    def test_partial_update_passes(self) -> None:
        serializer = PatientUpdateSerializer(data={"phone": "1122334455"})
        assert serializer.is_valid()
        assert serializer.validated_data["phone"] == "1122334455"

    def test_invalid_email_fails(self) -> None:
        serializer = PatientUpdateSerializer(data={"email": "not-an-email"})
        assert not serializer.is_valid()
        assert "email" in serializer.errors
