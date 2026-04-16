from typing import Any

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from dentora.accounts.models import User


class UserReadSerializer(serializers.ModelSerializer[User]):
    full_name = serializers.CharField(source="get_full_name", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "role",
            "is_active",
            "date_joined",
        ]
        read_only_fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "role",
            "is_active",
            "date_joined",
        ]


class UserCreateSerializer(serializers.Serializer):  # type: ignore[type-arg]
    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    role = serializers.ChoiceField(choices=User.Role.choices)

    def validate_email(self, value: str) -> str:
        return value.lower().strip()


class ChangePasswordSerializer(serializers.Serializer):  # type: ignore[type-arg]
    old_password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )
    new_password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )


class TokenPairWithUserSerializer(TokenObtainPairSerializer):
    """Extends the standard JWT pair serializer to include user data."""

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        data: dict[str, Any] = super().validate(attrs)
        data["user"] = UserReadSerializer(self.user).data
        return data
