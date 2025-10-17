import os

from django.apps import AppConfig
from django.conf import settings


class AuthConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.sys"
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "apps", "sys")

    def ready(self) -> None:
        from apps.sys.rolemanager import RoleManager

        setattr(settings, "CASBIN_ROLE_MANAGER", RoleManager())  # noqa: B010
