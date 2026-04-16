from django.urls import URLPattern, URLResolver, path

from dentora.patients import views

app_name = "patients"

urlpatterns: list[URLPattern | URLResolver] = [
    path(
        "patients/", views.PatientListCreateView.as_view(), name="patient-list-create"
    ),
    path(
        "patients/<str:pk>/", views.PatientDetailView.as_view(), name="patient-detail"
    ),
]
