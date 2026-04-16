from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from dentora.core.exceptions import ConflictError, NotFoundError
from dentora.patients import services
from dentora.patients.serializers import (
    PatientCreateSerializer,
    PatientReadSerializer,
    PatientUpdateSerializer,
)


@extend_schema(tags=["patients"])
class PatientListCreateView(APIView):
    """List active patients or register a new one."""

    permission_classes = (IsAuthenticated,)
    authentication_classes = (JWTAuthentication, SessionAuthentication)

    @extend_schema(
        summary="List patients",
        parameters=[
            OpenApiParameter(
                name="search",
                description=(
                    "Filter by first name, last name, DNI, or email (case-insensitive)."
                ),
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="include_inactive",
                description="Set to 'true' to include deactivated patients.",
                required=False,
                type=bool,
            ),
        ],
        responses={200: PatientReadSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        search = request.query_params.get("search", "")
        include_inactive = (
            request.query_params.get("include_inactive", "").lower() == "true"
        )
        patients = services.list_patients(
            search=search, include_inactive=include_inactive
        )
        serializer = PatientReadSerializer(patients, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Register a new patient",
        request=PatientCreateSerializer,
        responses={
            201: PatientReadSerializer,
            400: OpenApiResponse(description="Validation error"),
            409: OpenApiResponse(description="DNI already registered"),
        },
    )
    def post(self, request: Request) -> Response:
        serializer = PatientCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            patient = services.create_patient(**serializer.validated_data)
        except ConflictError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            PatientReadSerializer(patient).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["patients"])
class PatientDetailView(APIView):
    """Retrieve, update, or deactivate a single patient."""

    permission_classes = (IsAuthenticated,)
    authentication_classes = (JWTAuthentication, SessionAuthentication)

    @extend_schema(
        summary="Retrieve a patient",
        responses={
            200: PatientReadSerializer,
            404: OpenApiResponse(description="Patient not found"),
        },
    )
    def get(self, request: Request, pk: str) -> Response:
        try:
            patient = services.get_patient(pk)
        except NotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        return Response(PatientReadSerializer(patient).data)

    @extend_schema(
        summary="Update a patient",
        request=PatientUpdateSerializer,
        responses={
            200: PatientReadSerializer,
            400: OpenApiResponse(description="Validation error"),
            404: OpenApiResponse(description="Patient not found"),
        },
    )
    def patch(self, request: Request, pk: str) -> Response:
        try:
            patient = services.get_patient(pk)
        except NotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)

        serializer = PatientUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        patient = services.update_patient(patient, **serializer.validated_data)
        return Response(PatientReadSerializer(patient).data)

    @extend_schema(
        summary="Deactivate a patient",
        responses={
            200: PatientReadSerializer,
            404: OpenApiResponse(description="Patient not found"),
        },
    )
    def delete(self, request: Request, pk: str) -> Response:
        try:
            patient = services.deactivate_patient(pk)
        except NotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        return Response(PatientReadSerializer(patient).data)
