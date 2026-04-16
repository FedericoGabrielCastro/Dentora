import factory
from factory.django import DjangoModelFactory

from dentora.patients.models import Patient


class PatientFactory(DjangoModelFactory):
    class Meta:
        model = Patient

    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    dni = factory.Sequence(lambda n: f"{10000000 + n}")
    email = factory.Faker("email")
    phone = factory.Faker("phone_number")
    date_of_birth = factory.Faker("date_of_birth", minimum_age=18, maximum_age=90)
    address = factory.Faker("address")
    notes = ""
    is_active = True


class InactivePatientFactory(PatientFactory):
    is_active = False
