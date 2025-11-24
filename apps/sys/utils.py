import hashlib

# 关闭 Casbin 的调试日志
import logging
from datetime import datetime

import jwt
from casbin import Enforcer
from casbin_adapter.enforcer import enforcer
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest
from ninja.security import HttpBearer

from apps.sys.models import User


# 创建一个过滤器来过滤 Casbin 的 Request 日志
class CasbinLogFilter(logging.Filter):
    def filter(self, record):
        # 过滤掉包含 "Request:" 的日志
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            if 'Request:' in record.msg:
                return False
        if hasattr(record, 'getMessage'):
            msg = record.getMessage()
            if 'Request:' in msg:
                return False
        return True

# 禁用 Casbin 的所有日志输出
casbin_logger = logging.getLogger("casbin")
casbin_logger.setLevel(logging.CRITICAL)  # 设置为 CRITICAL 级别，几乎不输出任何日志
casbin_logger.disabled = True  # 完全禁用该 logger
casbin_logger.addFilter(CasbinLogFilter())  # 添加过滤器

# 也尝试禁用可能的其他 logger 名称
persist_logger = logging.getLogger("casbin.persist")
persist_logger.setLevel(logging.CRITICAL)
persist_logger.disabled = True
persist_logger.addFilter(CasbinLogFilter())

# 如果日志是通过根 logger 输出的，也添加过滤器
root_logger = logging.getLogger()
for handler in root_logger.handlers:
    handler.addFilter(CasbinLogFilter())


def get_enforcer() -> Enforcer:
    return enforcer


def get_password(password: str) -> str:
    """计算密码hash"""

    password = settings.SECRET_KEY + password
    return hashlib.sha1(password.encode()).hexdigest()


def get_captcha(captcha_text: str) -> str:
    """计算验证码hash"""

    captcha_text = settings.SECRET_KEY + captcha_text.lower()
    return hashlib.sha1(captcha_text.encode()).hexdigest()


def get_token(user: User, expires: datetime) -> str:
    """获取JWT令牌（用户登录token）"""

    token = {"id": user.pk, "username": user.username, "expires": expires.isoformat()}
    return jwt.encode(token, settings.SECRET_KEY, algorithm="HS256")


def generate_api_token(expires: datetime) -> str:
    """生成独立的API Token（不依赖用户账号）"""

    token = {
        "type": "api_token",
        "expires": expires.isoformat(),
    }
    return jwt.encode(token, settings.SECRET_KEY, algorithm="HS256")


def is_service_account(username: str, nickname: str | None = None) -> bool:
    """判断是否是服务账号"""
    return username.startswith("data-crawler") or ("服务账号" in (nickname or ""))


class AuthBearer(HttpBearer):
    """JWT认证（OR逻辑：满足任意一个权限即可）"""

    def __init__(self, perms: list[tuple[str, str]]):
        self._perms = perms
        super().__init__()

    def authenticate(self, request: HttpRequest, token):
        import logging
        logger = logging.getLogger(__name__)

        try:
            # 调试日志：记录收到的 token（不记录完整内容，只记录长度和前缀）
            logger.debug(f"AuthBearer received token (length: {len(token)}, prefix: {token[:20] if len(token) > 20 else token})")

            # HttpBearer 应该已经去掉了 "Bearer " 前缀，但如果还有，手动去掉
            if token.startswith("Bearer "):
                token = token[7:]

            login_token = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            logger.debug(f"AuthBearer decoded token successfully for user: {login_token.get('username', 'unknown')}")

            # 无需权限控制
            if not self._perms:
                return login_token

            enforcer.load_policy()

            # 只需要满足任意一项配置的权限（OR逻辑，向后兼容）
            for p in self._perms:
                obj = p[0].format(
                    username=login_token["username"],
                    **(request.resolver_match.kwargs if request.resolver_match else {}),
                )
                act = p[1]

                # 验证调用权限
                if enforcer.enforce(login_token["username"], obj, act):
                    return login_token

            # 所有权限验证都失败
            raise PermissionDenied("没有权限")
        except Exception as e:
            logger.warning(f"AuthBearer authentication failed: {type(e).__name__}: {str(e)}")
            return None


class AuthBearerAll(HttpBearer):
    """JWT认证（AND逻辑：需要满足所有权限）"""

    def __init__(self, perms: list[tuple[str, str]]):
        self._perms = perms
        super().__init__()

    def authenticate(self, request: HttpRequest, token):
        import logging
        logger = logging.getLogger(__name__)

        try:
            # 调试日志：记录收到的 token（不记录完整内容，只记录长度和前缀）
            logger.debug(f"AuthBearerAll received token (length: {len(token)}, prefix: {token[:20] if len(token) > 20 else token})")

            # HttpBearer 应该已经去掉了 "Bearer " 前缀，但如果还有，手动去掉
            if token.startswith("Bearer "):
                token = token[7:]

            login_token = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            logger.debug(f"AuthBearerAll decoded token successfully for user: {login_token.get('username', 'unknown')}")

            # 无需权限控制
            if not self._perms:
                return login_token

            enforcer.load_policy()

            # 需要满足所有配置的权限（AND逻辑）
            for p in self._perms:
                obj = p[0].format(
                    username=login_token["username"],
                    **(request.resolver_match.kwargs if request.resolver_match else {}),
                )
                act = p[1]

                # 验证调用权限
                if not enforcer.enforce(login_token["username"], obj, act):
                    # 任何一个权限验证失败，就拒绝访问
                    raise PermissionDenied(f"没有权限: {obj} {act}")

            # 所有权限验证都通过
            return login_token
        except Exception as e:
            logger.warning(f"AuthBearerAll authentication failed: {type(e).__name__}: {str(e)}")
            return None


class AuthBearerToken(HttpBearer):
    """JWT认证（仅验证token有效性，不验证权限，用于API token）"""

    def authenticate(self, request: HttpRequest, token):
        import logging
        logger = logging.getLogger(__name__)

        try:
            # 调试日志：记录收到的 token（不记录完整内容，只记录长度和前缀）
            logger.debug(f"AuthBearerToken received token (length: {len(token)}, prefix: {token[:20] if len(token) > 20 else token})")

            # HttpBearer 应该已经去掉了 "Bearer " 前缀，但如果还有，手动去掉
            if token.startswith("Bearer "):
                token = token[7:]

            # 只验证 token 是否有效，不验证权限
            decoded_token = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])

            # 检查是否是 API token（独立token，不依赖用户）
            if decoded_token.get("type") == "api_token":
                logger.debug("API token authenticated successfully (independent token)")
                return decoded_token

            # 兼容旧的用户token格式
            logger.debug(f"AuthBearerToken decoded token successfully for user: {decoded_token.get('username', 'unknown')}")
            return decoded_token
        except Exception as e:
            logger.warning(f"AuthBearerToken authentication failed: {type(e).__name__}: {str(e)}")
            return None


class AuthBearerTokenOrPerm(HttpBearer):
    """JWT认证（OR逻辑：API token认证或权限验证）

    支持两种认证方式：
    1. 如果是独立的 API token（type="api_token"），只验证token有效性，不验证权限
    2. 否则，验证用户是否有相应权限
    """

    def __init__(self, perms: list[tuple[str, str]]):
        self._perms = perms
        super().__init__()

    def authenticate(self, request: HttpRequest, token):
        import logging
        logger = logging.getLogger(__name__)

        try:
            # 调试日志：记录收到的 token（不记录完整内容，只记录长度和前缀）
            logger.debug(f"AuthBearerTokenOrPerm received token (length: {len(token)}, prefix: {token[:20] if len(token) > 20 else token})")

            # HttpBearer 应该已经去掉了 "Bearer " 前缀，但如果还有，手动去掉
            if token.startswith("Bearer "):
                token = token[7:]

            decoded_token = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])

            # 检查是否是独立的 API token（不依赖用户账号）
            if decoded_token.get("type") == "api_token":
                logger.debug("API token authenticated successfully (independent token), skipping permission check")
                return decoded_token

            # 普通用户token：需要验证权限
            username = decoded_token.get("username", "")
            logger.debug(f"AuthBearerTokenOrPerm decoded token successfully for user: {username}")

            if not self._perms:
                # 如果没有配置权限，直接通过
                return decoded_token

            enforcer.load_policy()

            # 只需要满足任意一项配置的权限（OR逻辑）
            for p in self._perms:
                obj = p[0].format(
                    username=username,
                    **(request.resolver_match.kwargs if request.resolver_match else {}),
                )
                act = p[1]

                # 验证调用权限
                if enforcer.enforce(username, obj, act):
                    logger.debug(f"Permission check passed: {obj} {act}")
                    return decoded_token

            # 所有权限验证都失败
            raise PermissionDenied("没有权限")
        except PermissionDenied:
            raise
        except Exception as e:
            logger.warning(f"AuthBearerTokenOrPerm authentication failed: {type(e).__name__}: {str(e)}")
            return None
