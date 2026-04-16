from rest_framework import serializers

from dentora.patients.models import Patient


class PatientReadSerializer(serializers.ModelSerializer[Patient]):
    full_name = serializers.CharField(source="get_full_name", read_only=True)

    class Meta:
        model = Patient
        fields = [
            "id",
            "first_name",
            "last_name",
            "full_name",
            "dni",
            "email",
            "phone",
            "date_of_birth",
            "address",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "full_name",
            "is_active",
            "created_at",
            "updated_at",
        ]


class PatientCreateSerializer(serializers.Serializer):  # type: ignore[type-arg]
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    dni = serializers.CharField(max_length=20)
    email = serializers.EmailField(required=False, default="")
    phone = serializers.CharField(max_length=30, required=False, default="")
    date_of_birth = serializers.DateField()
    address = serializers.CharField(required=False, default="", allow_blank=True)
    notes = serializers.CharField(required=False, default="", allow_blank=True)

    def validate_dni(self, value: str) -> str:
        return value.strip()

    def validate_first_name(self, value: str) -> str:
        return value.strip()

    def validate_last_name(self, value: str) -> str:
        return value.strip()


class PatientUpdateSerializer(serializers.Serializer):  # type: ignore[type-arg]
    first_name = serializers.CharField(max_length=150, required=False)
    last_name = serializers.CharField(max_length=150, required=False)
    email = serializers.EmailField(required=False)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False)
    address = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate_first_name(self, value: str) -> str:
        return value.strip()

    def validate_last_name(self, value: str) -> str:
        return value.strip()
