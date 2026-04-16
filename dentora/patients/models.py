import logging
from uuid import uuid4

from django.db import models

logger = logging.getLogger(__name__)


class Patient(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False,
        verbose_name="ID",
    )
    first_name = models.CharField(max_length=150, verbose_name="first name")
    last_name = models.CharField(max_length=150, verbose_name="last name")
    dni = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="DNI",
        help_text="National identity document number.",
    )
    email = models.EmailField(
        blank=True,
        verbose_name="email address",
        help_text="Contact email address for the patient.",
    )
    phone = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="phone number",
        help_text="Contact phone number for the patient.",
    )
    date_of_birth = models.DateField(verbose_name="date of birth")
    address = models.TextField(
        blank=True,
        verbose_name="address",
        help_text="Full postal address of the patient.",
    )
    notes = models.TextField(
        blank=True,
        verbose_name="notes",
        help_text="Internal clinical notes about the patient.",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="active",
        help_text="Inactive patients are not shown in default listings.",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="created at")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="updated at")

    class Meta:
        ordering = ["last_name", "first_name"]
        verbose_name = "patient"
        verbose_name_plural = "patients"

    def __str__(self) -> str:
        return f"{self.last_name}, {self.first_name} (DNI: {self.dni})"

    def get_full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
