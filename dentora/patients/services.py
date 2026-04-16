import logging
from typing import Any

from django.db import transaction
from django.db.models import Q, QuerySet

from dentora.core.exceptions import ConflictError, NotFoundError
from dentora.patients.models import Patient

logger = logging.getLogger(__name__)


def list_patients(
    search: str = "",
    include_inactive: bool = False,
) -> QuerySet[Patient]:
    """
    Return a queryset of patients, optionally filtered by a search term.

    The search term matches against first name, last name, DNI, and email.
    Inactive patients are excluded unless include_inactive is True.
    """
    qs = Patient.objects.all()
    if not include_inactive:
        qs = qs.filter(is_active=True)
    if search:
        qs = qs.filter(
            Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(dni__icontains=search)
            | Q(email__icontains=search)
        )
    return qs


def get_patient(patient_id: Any) -> Patient:
    """
    Return a patient by primary key.

    Raises NotFoundError if no patient exists with the given ID.
    """
    try:
        return Patient.objects.get(pk=patient_id)
    except Patient.DoesNotExist:
        raise NotFoundError(f"Patient '{patient_id}' does not exist.")


def create_patient(
    first_name: str,
    last_name: str,
    dni: str,
    date_of_birth: Any,
    email: str = "",
    phone: str = "",
    address: str = "",
    notes: str = "",
) -> Patient:
    """
    Create a new patient record.

    Raises ConflictError if a patient with the same DNI already exists.
    """
    if Patient.objects.filter(dni=dni).exists():
        raise ConflictError(f"A patient with DNI '{dni}' already exists.")

    with transaction.atomic():
        patient = Patient.objects.create(
            first_name=first_name,
            last_name=last_name,
            dni=dni,
            email=email,
            phone=phone,
            date_of_birth=date_of_birth,
            address=address,
            notes=notes,
        )

    logger.info("Patient created: %s (DNI=%s)", patient.get_full_name(), dni)
    return patient


def update_patient(patient: Patient, **kwargs: Any) -> Patient:
    """
    Update editable fields on an existing patient.

    Only fields present in kwargs are updated. DNI is not updatable.
    """
    allowed_fields = {
        "first_name",
        "last_name",
        "email",
        "phone",
        "date_of_birth",
        "address",
        "notes",
    }
    fields_to_update = []
    for field, value in kwargs.items():
        if field in allowed_fields:
            setattr(patient, field, value)
            fields_to_update.append(field)

    if fields_to_update:
        with transaction.atomic():
            patient.save(update_fields=fields_to_update + ["updated_at"])
        logger.info(
            "Patient updated: %s — fields: %s",
            patient.get_full_name(),
            fields_to_update,
        )
    return patient


def deactivate_patient(patient_id: Any) -> Patient:
    """
    Soft-delete a patient by setting is_active to False.

    Raises NotFoundError if no patient exists with the given ID.
    """
    patient = get_patient(patient_id)
    with transaction.atomic():
        patient.is_active = False
        patient.save(update_fields=["is_active", "updated_at"])
    logger.info("Patient deactivated: %s (id=%s)", patient.get_full_name(), patient_id)
    return patient
