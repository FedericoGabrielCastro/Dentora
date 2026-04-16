from django.contrib import admin
from django.contrib.auth.models import Group


# Unregister Group from admin — not needed for this project
admin.site.unregister(Group)
