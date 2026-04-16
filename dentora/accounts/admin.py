from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from dentora.accounts.models import User


@admin.register(User)
# User extends AbstractBaseUser, not AbstractUser — generic param not applicable.
class UserAdmin(BaseUserAdmin):  # type: ignore[type-arg]
    list_display = ["id", "email", "first_name", "last_name", "role", "is_active"]
    list_filter = ["role", "is_active"]
    search_fields = ["email", "first_name", "last_name"]
    ordering = ["last_name", "first_name"]

    fieldsets = (
        (None, {"fields": ("id", "email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "role")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "role",
                    "password1",
                    "password2",
                ),
            },
        ),
    )
    readonly_fields = ["id", "email", "password", "role", "date_joined", "last_login"]
