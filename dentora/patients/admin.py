from django.contrib import admin

from dentora.patients.models import Patient


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = [
        "id",
        "last_name",
        "first_name",
        "dni",
        "email",
        "phone",
        "is_active",
    ]
    list_filter = ["is_active"]
    search_fields = ["first_name", "last_name", "dni", "email"]
    ordering = ["last_name", "first_name"]
    readonly_fields = ["id", "created_at", "updated_at"]

    fieldsets = (
        (None, {"fields": ("id",)}),
        (
            "Personal info",
            {"fields": ("first_name", "last_name", "dni", "date_of_birth")},
        ),
        ("Contact", {"fields": ("email", "phone", "address")}),
        ("Clinical", {"fields": ("notes",)}),
        ("Status", {"fields": ("is_active",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
