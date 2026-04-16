from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from dentora.accounts.models import User


class IsAdmin(BasePermission):
    """Allows access only to users with the Admin role."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and isinstance(request.user, User)
            and request.user.role == User.Role.ADMIN
        )


class IsReceptionist(BasePermission):
    """Allows access only to users with the Receptionist role."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and isinstance(request.user, User)
            and request.user.role == User.Role.RECEPTIONIST
        )


class IsDentist(BasePermission):
    """Allows access only to users with the Dentist role."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and isinstance(request.user, User)
            and request.user.role == User.Role.DENTIST
        )


class IsAdminOrReceptionist(BasePermission):
    """Allows access to Admin or Receptionist users."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and isinstance(request.user, User)
            and request.user.role in {User.Role.ADMIN, User.Role.RECEPTIONIST}
        )
