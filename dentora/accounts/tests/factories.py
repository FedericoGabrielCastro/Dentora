import factory
from django.contrib.auth.hashers import make_password
from factory.django import DjangoModelFactory

from dentora.accounts.models import User

DEFAULT_PASSWORD = "TestPass123!"


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    role = User.Role.RECEPTIONIST
    password = factory.LazyFunction(lambda: make_password(DEFAULT_PASSWORD))
    is_active = True
    is_staff = False


class AdminUserFactory(UserFactory):
    role = User.Role.ADMIN
    is_staff = True


class DentistUserFactory(UserFactory):
    role = User.Role.DENTIST


class ReceptionistUserFactory(UserFactory):
    role = User.Role.RECEPTIONIST
