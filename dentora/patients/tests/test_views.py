import pytest
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from dentora.accounts.tests.factories import UserFactory
from dentora.patients.models import Patient
from dentora.patients.tests.factories import InactivePatientFactory, PatientFactory


def auth_client(user: object) -> APIClient:
    """Return an authenticated APIClient for the given user."""
    client = APIClient()
    refresh = RefreshToken.for_user(user)  # type: ignore[arg-type]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


@pytest.mark.django_db
class TestPatientListCreateView:
    url = "/api/patients/"

    def test_unauthenticated_returns_401(self, api_client: APIClient) -> None:
        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_returns_active_patients(self) -> None:
        user = UserFactory()
        PatientFactory.create_batch(3)
        InactivePatientFactory()
        response = auth_client(user).get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 3

    def test_list_search_filters_results(self) -> None:
        user = UserFactory()
        PatientFactory(last_name="Gomez")
        PatientFactory(last_name="Torres")
        response = auth_client(user).get(self.url, {"search": "Gom"})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["last_name"] == "Gomez"

    def test_list_include_inactive(self) -> None:
        user = UserFactory()
        PatientFactory()
        InactivePatientFactory()
        response = auth_client(user).get(self.url, {"include_inactive": "true"})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_create_patient_returns_201(self) -> None:
        user = UserFactory()
        payload = {
            "first_name": "Ana",
            "last_name": "Gomez",
            "dni": "12345678",
            "date_of_birth": "1990-05-15",
            "email": "ana@example.com",
            "phone": "1122334455",
        }
        response = auth_client(user).post(self.url, data=payload)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["dni"] == "12345678"
        assert response.data["full_name"] == "Ana Gomez"
        assert Patient.objects.filter(dni="12345678").exists()

    def test_create_duplicate_dni_returns_409(self) -> None:
        user = UserFactory()
        PatientFactory(dni="12345678")
        payload = {
            "first_name": "Pedro",
            "last_name": "Lopez",
            "dni": "12345678",
            "date_of_birth": "1985-01-01",
        }
        response = auth_client(user).post(self.url, data=payload)
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_create_missing_fields_returns_400(self) -> None:
        user = UserFactory()
        response = auth_client(user).post(self.url, data={})
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestPatientDetailView:
    def _url(self, pk: object) -> str:
        return f"/api/patients/{pk}/"

    def test_unauthenticated_returns_401(self, api_client: APIClient) -> None:
        patient = PatientFactory()
        response = api_client.get(self._url(patient.pk))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_retrieve_existing_patient(self) -> None:
        user = UserFactory()
        patient = PatientFactory(first_name="Ana", last_name="Gomez")
        response = auth_client(user).get(self._url(patient.pk))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == str(patient.pk)
        assert response.data["full_name"] == "Ana Gomez"

    def test_retrieve_nonexistent_returns_404(self) -> None:
        import uuid

        user = UserFactory()
        response = auth_client(user).get(self._url(uuid.uuid4()))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_patch_updates_patient(self) -> None:
        user = UserFactory()
        patient = PatientFactory(phone="0000000000")
        response = auth_client(user).patch(
            self._url(patient.pk), data={"phone": "9988776655"}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["phone"] == "9988776655"
        patient.refresh_from_db()
        assert patient.phone == "9988776655"

    def test_patch_invalid_data_returns_400(self) -> None:
        user = UserFactory()
        patient = PatientFactory()
        response = auth_client(user).patch(
            self._url(patient.pk), data={"email": "not-an-email"}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_patch_nonexistent_returns_404(self) -> None:
        import uuid

        user = UserFactory()
        response = auth_client(user).patch(
            self._url(uuid.uuid4()), data={"phone": "1234567890"}
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_deactivates_patient(self) -> None:
        user = UserFactory()
        patient = PatientFactory()
        response = auth_client(user).delete(self._url(patient.pk))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_active"] is False
        patient.refresh_from_db()
        assert patient.is_active is False

    def test_delete_nonexistent_returns_404(self) -> None:
        import uuid

        user = UserFactory()
        response = auth_client(user).delete(self._url(uuid.uuid4()))
        assert response.status_code == status.HTTP_404_NOT_FOUND
