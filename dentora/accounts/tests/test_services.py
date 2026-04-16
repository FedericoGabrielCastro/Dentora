import pytest

from dentora.accounts.models import User
from dentora.accounts.tests.factories import UserFactory, DEFAULT_PASSWORD
from dentora.accounts import services
from dentora.core.exceptions import ConflictError, ValidationError


@pytest.mark.django_db
class TestCreateUser:
    def test_creates_user_successfully(self) -> None:
        user = services.create_user(
            email="new@example.com",
            password="StrongPass123!",
            role=User.Role.RECEPTIONIST,
            first_name="Jane",
            last_name="Doe",
        )
        assert user.pk is not None
        assert user.email == "new@example.com"
        assert user.role == User.Role.RECEPTIONIST
        assert user.first_name == "Jane"
        assert user.last_name == "Doe"
        assert user.is_active is True
        assert user.check_password("StrongPass123!")

    def test_duplicate_email_raises_conflict(self) -> None:
        UserFactory(email="existing@example.com")
        with pytest.raises(ConflictError):
            services.create_user(
                email="existing@example.com",
                password="StrongPass123!",
                role=User.Role.DENTIST,
                first_name="Bob",
                last_name="Smith",
            )

    def test_weak_password_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            services.create_user(
                email="weak@example.com",
                password="123",
                role=User.Role.RECEPTIONIST,
                first_name="Jane",
                last_name="Doe",
            )

    def test_persists_to_database(self) -> None:
        services.create_user(
            email="persisted@example.com",
            password="StrongPass123!",
            role=User.Role.ADMIN,
            first_name="Alice",
            last_name="Admin",
        )
        assert User.objects.filter(email="persisted@example.com").exists()


@pytest.mark.django_db
class TestChangePassword:
    def test_changes_password_successfully(self) -> None:
        user = UserFactory()
        services.change_password(
            user=user,
            old_password=DEFAULT_PASSWORD,
            new_password="NewStrongPass456!",
        )
        user.refresh_from_db()
        assert user.check_password("NewStrongPass456!")

    def test_wrong_old_password_raises_validation_error(self) -> None:
        user = UserFactory()
        with pytest.raises(ValidationError, match="Current password is incorrect"):
            services.change_password(
                user=user,
                old_password="WrongPassword!",
                new_password="NewStrongPass456!",
            )

    def test_weak_new_password_raises_validation_error(self) -> None:
        user = UserFactory()
        with pytest.raises(ValidationError):
            services.change_password(
                user=user,
                old_password=DEFAULT_PASSWORD,
                new_password="123",
            )
