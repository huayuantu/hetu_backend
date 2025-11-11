import os
import logging

from django.apps import AppConfig
from django.conf import settings


class AuthConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.sys"
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "apps", "sys")

    def ready(self) -> None:
        from apps.sys.rolemanager import RoleManager

        setattr(settings, "CASBIN_ROLE_MANAGER", RoleManager())  # noqa: B010
        
        # 禁用 Casbin 的调试日志
        casbin_logger = logging.getLogger("casbin")
        casbin_logger.setLevel(logging.CRITICAL)
        casbin_logger.disabled = True
        
        persist_logger = logging.getLogger("casbin.persist")
        persist_logger.setLevel(logging.CRITICAL)
        persist_logger.disabled = True
