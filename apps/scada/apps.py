import os

from django.apps import AppConfig


class GrmConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"  # pyright: ignore[reportAssignmentType]
    name = "apps.scada"
    path = os.path.dirname(__file__)
