import pytest
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from dentora.accounts.models import User
from dentora.accounts.tests.factories import (
    AdminUserFactory,
    DentistUserFactory,
    UserFactory,
    DEFAULT_PASSWORD,
)


def get_tokens_for_user(user: User) -> tuple[str, str]:
    """Return (access_token, refresh_token) for a given user."""
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token), str(refresh)


@pytest.mark.django_db
class TestLoginView:
    url = "/api/auth/login/"

    def test_login_returns_tokens_and_user(self, api_client: APIClient) -> None:
        UserFactory(email="login@example.com")
        response = api_client.post(
            self.url,
            {"email": "login@example.com", "password": DEFAULT_PASSWORD},
        )
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data
        assert response.data["user"]["email"] == "login@example.com"

    def test_wrong_password_returns_401(self, api_client: APIClient) -> None:
        UserFactory(email="login@example.com")
        response = api_client.post(
            self.url,
            {"email": "login@example.com", "password": "WrongPassword!"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_inactive_user_returns_401(self, api_client: APIClient) -> None:
        UserFactory(email="inactive@example.com", is_active=False)
        response = api_client.post(
            self.url,
            {"email": "inactive@example.com", "password": DEFAULT_PASSWORD},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_missing_credentials_returns_400(self, api_client: APIClient) -> None:
        response = api_client.post(self.url, {})
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestLogoutView:
    url = "/api/auth/logout/"

    def test_logout_blacklists_refresh_token(self, api_client: APIClient) -> None:
        user = UserFactory()
        access, refresh = get_tokens_for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = api_client.post(self.url, {"refresh": refresh})
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_logout_with_missing_refresh_returns_400(
        self, api_client: APIClient
    ) -> None:
        user = UserFactory()
        access, _ = get_tokens_for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = api_client.post(self.url, {})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_logout_requires_authentication(self, api_client: APIClient) -> None:
        response = api_client.post(self.url, {"refresh": "sometoken"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestMeView:
    url = "/api/auth/me/"

    def test_returns_current_user(self, api_client: APIClient) -> None:
        user = UserFactory(
            email="me@example.com", first_name="Ada", last_name="Lovelace"
        )
        access, _ = get_tokens_for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == "me@example.com"
        assert response.data["full_name"] == "Ada Lovelace"

    def test_requires_authentication(self, api_client: APIClient) -> None:
        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestChangePasswordView:
    url = "/api/auth/change-password/"

    def test_changes_password_successfully(self, api_client: APIClient) -> None:
        user = UserFactory()
        access, _ = get_tokens_for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = api_client.post(
            self.url,
            {"old_password": DEFAULT_PASSWORD, "new_password": "NewStrongPass456!"},
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        user.refresh_from_db()
        assert user.check_password("NewStrongPass456!")

    def test_wrong_old_password_returns_400(self, api_client: APIClient) -> None:
        user = UserFactory()
        access, _ = get_tokens_for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = api_client.post(
            self.url,
            {"old_password": "WrongPassword!", "new_password": "NewStrongPass456!"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_requires_authentication(self, api_client: APIClient) -> None:
        response = api_client.post(
            self.url,
            {"old_password": DEFAULT_PASSWORD, "new_password": "NewPass456!"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestUserListCreateView:
    url = "/api/users/"

    def _admin_client(self, api_client: APIClient) -> tuple[APIClient, User]:
        admin = AdminUserFactory()
        access, _ = get_tokens_for_user(admin)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        return api_client, admin

    def test_admin_can_list_users(self, api_client: APIClient) -> None:
        UserFactory.create_batch(3)
        client, admin = self._admin_client(api_client)
        response = client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        # 3 created + the admin itself
        assert len(response.data) == 4

    def test_admin_can_create_user(self, api_client: APIClient) -> None:
        client, _ = self._admin_client(api_client)
        payload = {
            "email": "new.user@example.com",
            "password": "StrongPass123!",
            "first_name": "New",
            "last_name": "User",
            "role": User.Role.RECEPTIONIST,
        }
        response = client.post(self.url, payload)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["email"] == "new.user@example.com"
        assert response.data["role"] == User.Role.RECEPTIONIST
        assert "password" not in response.data

    def test_duplicate_email_returns_409(self, api_client: APIClient) -> None:
        UserFactory(email="taken@example.com")
        client, _ = self._admin_client(api_client)
        payload = {
            "email": "taken@example.com",
            "password": "StrongPass123!",
            "first_name": "Jane",
            "last_name": "Doe",
            "role": User.Role.DENTIST,
        }
        response = client.post(self.url, payload)
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_non_admin_cannot_list_users(self, api_client: APIClient) -> None:
        dentist = DentistUserFactory()
        access, _ = get_tokens_for_user(dentist)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_cannot_list_users(self, api_client: APIClient) -> None:
        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
