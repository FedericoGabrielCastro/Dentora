import pytest

from dentora.accounts.models import User
from dentora.accounts.tests.factories import (
    AdminUserFactory,
    DentistUserFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestUserModel:
    def test_str_representation(self) -> None:
        user = UserFactory(
            first_name="Ada", last_name="Lovelace", email="ada@example.com"
        )
        assert str(user) == "Ada Lovelace <ada@example.com>"

    def test_get_full_name(self) -> None:
        user = UserFactory(first_name="Ada", last_name="Lovelace")
        assert user.get_full_name() == "Ada Lovelace"

    def test_email_is_unique(self) -> None:
        UserFactory(email="duplicate@example.com")
        with pytest.raises(Exception):
            UserFactory(email="duplicate@example.com")

    def test_default_is_active(self) -> None:
        user = UserFactory()
        assert user.is_active is True

    def test_roles_are_valid(self) -> None:
        admin = AdminUserFactory()
        dentist = DentistUserFactory()
        receptionist = UserFactory(role=User.Role.RECEPTIONIST)

        assert admin.role == User.Role.ADMIN
        assert dentist.role == User.Role.DENTIST
        assert receptionist.role == User.Role.RECEPTIONIST

    def test_role_display(self) -> None:
        user = UserFactory(role=User.Role.RECEPTIONIST)
        assert user.get_role_display() == "Receptionist"


@pytest.mark.django_db
class TestUserManager:
    def test_create_user(self) -> None:
        user = User.objects.create_user(
            email="new@example.com",
            password="StrongPass123!",
            role=User.Role.RECEPTIONIST,
            first_name="Jane",
            last_name="Doe",
        )
        assert user.email == "new@example.com"
        assert user.role == User.Role.RECEPTIONIST
        assert user.check_password("StrongPass123!")
        assert not user.is_staff
        assert not user.is_superuser

    def test_create_user_normalizes_email(self) -> None:
        user = User.objects.create_user(
            email="USER@EXAMPLE.COM",
            password="StrongPass123!",
            role=User.Role.DENTIST,
            first_name="Bob",
            last_name="Smith",
        )
        assert user.email == "user@example.com"

    def test_create_user_requires_email(self) -> None:
        with pytest.raises(ValueError, match="Email address is required"):
            User.objects.create_user(
                email="",
                password="StrongPass123!",
                role=User.Role.RECEPTIONIST,
                first_name="Jane",
                last_name="Doe",
            )

    def test_create_superuser(self) -> None:
        user = User.objects.create_superuser(
            email="super@example.com",
            password="StrongPass123!",
            first_name="Super",
            last_name="Admin",
        )
        assert user.is_staff is True
        assert user.is_superuser is True
        assert user.role == User.Role.ADMIN
