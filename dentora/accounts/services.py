import logging

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction

from dentora.accounts.models import User
from dentora.core.exceptions import ConflictError, ValidationError

logger = logging.getLogger(__name__)


def create_user(
    email: str,
    password: str,
    role: str,
    first_name: str,
    last_name: str,
) -> User:
    """
    Create a new clinic user.

    Raises ConflictError if the email is already registered.
    Raises ValidationError if the password does not meet Django's validators.
    """
    if User.objects.filter(email=email).exists():
        raise ConflictError(f"A user with email '{email}' already exists.")

    try:
        validate_password(password)
    except DjangoValidationError as exc:
        raise ValidationError("; ".join(exc.messages)) from exc

    with transaction.atomic():
        user = User.objects.create_user(
            email=email,
            password=password,
            role=role,
            first_name=first_name,
            last_name=last_name,
        )

    logger.info("User created: %s (role=%s)", email, role)
    return user


def change_password(user: User, old_password: str, new_password: str) -> None:
    """
    Change a user's password after verifying the current one.

    Raises ValidationError if the old password is wrong or the new one
    does not meet Django's password validators.
    """
    if not user.check_password(old_password):
        raise ValidationError("Current password is incorrect.")

    try:
        validate_password(new_password, user=user)
    except DjangoValidationError as exc:
        raise ValidationError("; ".join(exc.messages)) from exc

    user.set_password(new_password)
    user.save(update_fields=["password"])
    logger.info("Password changed for user: %s", user.email)
