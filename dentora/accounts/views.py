import logging
from typing import Any, cast

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.views import TokenRefreshView as BaseTokenRefreshView

from dentora.accounts.models import User
from dentora.accounts.permissions import IsAdmin
from dentora.accounts.serializers import (
    ChangePasswordSerializer,
    TokenPairWithUserSerializer,
    UserCreateSerializer,
    UserReadSerializer,
)
from dentora.accounts import services
from dentora.core.exceptions import ConflictError, ValidationError

logger = logging.getLogger(__name__)


@extend_schema(tags=["auth"])
class LoginView(TokenObtainPairView):
    """Obtain a JWT access + refresh token pair."""

    serializer_class = TokenPairWithUserSerializer
    # simplejwt stubs type permission_classes as tuple[()] on TokenViewBase.
    permission_classes = (AllowAny,)  # type: ignore[assignment]
    authentication_classes = ()

    @extend_schema(
        summary="Login — obtain JWT token pair",
        responses={
            200: TokenPairWithUserSerializer,
            401: OpenApiResponse(description="Invalid credentials"),
        },
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().post(request, *args, **kwargs)


@extend_schema(tags=["auth"])
class TokenRefreshView(BaseTokenRefreshView):
    """Refresh an access token using a valid refresh token."""

    # simplejwt stubs type permission_classes as tuple[()] on TokenViewBase.
    permission_classes = (AllowAny,)  # type: ignore[assignment]
    authentication_classes = ()

    @extend_schema(
        summary="Refresh access token",
        responses={
            200: OpenApiResponse(description="New access token"),
            401: OpenApiResponse(description="Refresh token invalid or expired"),
        },
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().post(request, *args, **kwargs)


@extend_schema(tags=["auth"])
class LogoutView(APIView):
    """Blacklist a refresh token, effectively logging the user out."""

    permission_classes = (IsAuthenticated,)
    authentication_classes = (JWTAuthentication,)

    @extend_schema(
        summary="Logout — blacklist refresh token",
        request=None,
        responses={
            204: OpenApiResponse(description="Logged out successfully"),
            400: OpenApiResponse(description="Invalid or missing refresh token"),
        },
    )
    def post(self, request: Request) -> Response:
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"detail": "refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["auth"])
class MeView(APIView):
    """Retrieve the authenticated user's own profile."""

    permission_classes = (IsAuthenticated,)
    authentication_classes = (JWTAuthentication,)

    @extend_schema(
        summary="Get current user profile",
        responses={200: UserReadSerializer},
    )
    def get(self, request: Request) -> Response:
        serializer = UserReadSerializer(cast(User, request.user))
        return Response(serializer.data)


@extend_schema(tags=["auth"])
class ChangePasswordView(APIView):
    """Change the authenticated user's password."""

    permission_classes = (IsAuthenticated,)
    authentication_classes = (JWTAuthentication,)

    @extend_schema(
        summary="Change password",
        request=ChangePasswordSerializer,
        responses={
            204: OpenApiResponse(description="Password changed successfully"),
            400: OpenApiResponse(description="Validation error"),
        },
    )
    def post(self, request: Request) -> Response:
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            services.change_password(
                user=cast(User, request.user),
                old_password=serializer.validated_data["old_password"],
                new_password=serializer.validated_data["new_password"],
            )
        except ValidationError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["users"])
class UserListCreateView(APIView):
    """List all users or create a new one (admin only)."""

    permission_classes = (IsAuthenticated, IsAdmin)
    authentication_classes = (JWTAuthentication,)

    @extend_schema(
        summary="List all users",
        responses={200: UserReadSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        users = User.objects.all()
        serializer = UserReadSerializer(users, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Create a new user",
        request=UserCreateSerializer,
        responses={
            201: UserReadSerializer,
            400: OpenApiResponse(description="Validation error"),
            409: OpenApiResponse(description="Email already registered"),
        },
    )
    def post(self, request: Request) -> Response:
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user = services.create_user(**serializer.validated_data)
        except ConflictError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_409_CONFLICT,
            )
        except ValidationError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            UserReadSerializer(user).data,
            status=status.HTTP_201_CREATED,
        )
