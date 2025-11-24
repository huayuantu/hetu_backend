"""服务账号管理API"""

from datetime import UTC, datetime, timedelta

from casbin_adapter.enforcer import enforcer
from django.shortcuts import get_object_or_404
from ninja import Router
from ninja.errors import HttpError
from pydantic import BaseModel

from apps.sys.models import User
from apps.sys.utils import AuthBearer, get_token
from utils.schema.base import api_schema

router = Router()


class GenerateTokenIn(BaseModel):
    """生成token请求"""

    username: str
    expires_days: int = 365


class GenerateTokenOut(BaseModel):
    """生成token响应"""

    username: str
    token: str
    expires: datetime
    token_type: str = "Bearer"


@router.post("/generate-token", response=GenerateTokenOut, auth=AuthBearer([("sys:user:edit", "x")]))
@api_schema
def generate_token(request, payload: GenerateTokenIn):
    """
    为服务账号生成长期token

    需要权限: sys:user:edit
    """
    user = get_object_or_404(User, username=payload.username, status=1)

    # 检查是否是服务账号（通过用户名前缀或昵称判断）
    if not (user.username.startswith("data-crawler") or "服务账号" in (user.nickname or "")):
        raise HttpError(
            400,
            f"用户 '{payload.username}' 不是服务账号。"
            "服务账号用户名应以 'data-crawler' 开头或昵称包含 '服务账号'",
        )

    expires = datetime.now(UTC) + timedelta(days=payload.expires_days)
    token = get_token(user, expires)

    return GenerateTokenOut(
        username=user.username,
        token=token,
        expires=expires,
        token_type="Bearer",
    )


class AddSitePermissionIn(BaseModel):
    """添加站点权限请求"""

    username: str
    site_id: int


@router.post("/add-site-permission", response=dict, auth=AuthBearer([("sys:user:edit", "x")]))
@api_schema
def add_site_permission(request, payload: AddSitePermissionIn):
    """
    为服务账号添加站点权限

    需要权限: sys:user:edit
    """
    user = get_object_or_404(User, username=payload.username, status=1)

    enforcer.load_policy()
    site_permit_obj = f"scada:site:permit:{payload.site_id}"

    # 添加读写权限
    if not enforcer.enforce(user.username, site_permit_obj, "w"):
        enforcer.add_policy(user.username, site_permit_obj, "w")
    if not enforcer.enforce(user.username, site_permit_obj, "r"):
        enforcer.add_policy(user.username, site_permit_obj, "r")

    return {
        "username": user.username,
        "site_id": payload.site_id,
        "permission": site_permit_obj,
        "message": "站点权限已添加",
    }

