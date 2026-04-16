import logging
from typing import Any
from uuid import uuid4

from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models

logger = logging.getLogger(__name__)


class UserManager(BaseUserManager["User"]):
    use_in_migrations = True

    def create_user(
        self,
        email: str,
        password: str | None = None,
        **extra_fields: Any,
    ) -> "User":
        if not email:
            raise ValueError("Email address is required.")
        email = self.normalize_email(email.lower())
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self,
        email: str,
        password: str | None = None,
        **extra_fields: Any,
    ) -> "User":
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "admin")

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        RECEPTIONIST = "receptionist", "Receptionist"
        DENTIST = "dentist", "Dentist"

    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False,
        verbose_name="ID",
    )
    email = models.EmailField(
        unique=True,
        verbose_name="email address",
    )
    first_name = models.CharField(
        max_length=150,
        verbose_name="first name",
    )
    last_name = models.CharField(
        max_length=150,
        verbose_name="last name",
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        verbose_name="role",
        help_text="User role within the clinic (admin, receptionist, or dentist).",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="active",
        help_text="Designates whether this user should be treated as active.",
    )
    is_staff = models.BooleanField(
        default=False,
        verbose_name="staff status",
        help_text="Designates whether the user can log into the admin site.",
    )
    date_joined = models.DateTimeField(
        auto_now_add=True,
        verbose_name="date joined",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name", "role"]

    objects = UserManager()

    class Meta:
        ordering = ["last_name", "first_name"]
        verbose_name = "user"
        verbose_name_plural = "users"

    def __str__(self) -> str:
        return f"{self.get_full_name()} <{self.email}>"

    def get_full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()
