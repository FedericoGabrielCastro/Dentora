import pytest

from dentora.accounts.models import User
from dentora.accounts.serializers import (
    ChangePasswordSerializer,
    UserCreateSerializer,
    UserReadSerializer,
)
from dentora.accounts.tests.factories import UserFactory


@pytest.mark.django_db
class TestUserReadSerializer:
    def test_output_shape(self) -> None:
        user = UserFactory(
            email="ada@example.com",
            first_name="Ada",
            last_name="Lovelace",
            role=User.Role.ADMIN,
        )
        data = UserReadSerializer(user).data
        assert set(data.keys()) == {
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "role",
            "is_active",
            "date_joined",
        }
        assert data["email"] == "ada@example.com"
        assert data["full_name"] == "Ada Lovelace"
        assert data["role"] == User.Role.ADMIN

    def test_password_not_exposed(self) -> None:
        user = UserFactory()
        data = UserReadSerializer(user).data
        assert "password" not in data


class TestUserCreateSerializer:
    def test_valid_data(self) -> None:
        payload = {
            "email": "new@example.com",
            "password": "StrongPass123!",
            "first_name": "Jane",
            "last_name": "Doe",
            "role": User.Role.RECEPTIONIST,
        }
        serializer = UserCreateSerializer(data=payload)
        assert serializer.is_valid(), serializer.errors

    def test_email_is_lowercased(self) -> None:
        payload = {
            "email": "NEW@EXAMPLE.COM",
            "password": "StrongPass123!",
            "first_name": "Jane",
            "last_name": "Doe",
            "role": User.Role.RECEPTIONIST,
        }
        serializer = UserCreateSerializer(data=payload)
        assert serializer.is_valid()
        assert serializer.validated_data["email"] == "new@example.com"

    def test_invalid_role(self) -> None:
        payload = {
            "email": "user@example.com",
            "password": "StrongPass123!",
            "first_name": "Jane",
            "last_name": "Doe",
            "role": "supervillain",
        }
        serializer = UserCreateSerializer(data=payload)
        assert not serializer.is_valid()
        assert "role" in serializer.errors

    def test_missing_required_fields(self) -> None:
        serializer = UserCreateSerializer(data={})
        assert not serializer.is_valid()
        assert "email" in serializer.errors
        assert "password" in serializer.errors
        assert "first_name" in serializer.errors
        assert "last_name" in serializer.errors
        assert "role" in serializer.errors

    def test_invalid_email_format(self) -> None:
        payload = {
            "email": "not-an-email",
            "password": "StrongPass123!",
            "first_name": "Jane",
            "last_name": "Doe",
            "role": User.Role.RECEPTIONIST,
        }
        serializer = UserCreateSerializer(data=payload)
        assert not serializer.is_valid()
        assert "email" in serializer.errors


class TestChangePasswordSerializer:
    def test_valid_data(self) -> None:
        serializer = ChangePasswordSerializer(
            data={"old_password": "OldPass123!", "new_password": "NewPass456!"}
        )
        assert serializer.is_valid(), serializer.errors

    def test_missing_fields(self) -> None:
        serializer = ChangePasswordSerializer(data={})
        assert not serializer.is_valid()
        assert "old_password" in serializer.errors
        assert "new_password" in serializer.errors
