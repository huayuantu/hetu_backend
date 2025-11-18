import logging

from django.conf import settings
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Router
from ninja.errors import HttpError
from ninja.files import UploadedFile
from oss2 import Bucket, ProviderAuth
from oss2.credentials import EnvironmentVariableCredentialsProvider

from apps.scada.models import AppUpdate, UpdateLog
from apps.scada.schema.update import (
    AppUpdateCheckOut,
    AppUpdateIn,
    AppUpdateOut,
    UpdateLogIn,
    UpdateLogOut,
)
from utils.schema.base import api_schema
from utils.schema.paginate import api_paginate

router = Router()
logger = logging.getLogger(__name__)

# OSS配置（从settings读取）
auth = ProviderAuth(EnvironmentVariableCredentialsProvider())
oss_endpoint = settings.OSS_ENDPOINT
oss_bucket_name = settings.OSS_BUCKET_NAME
bucket = Bucket(auth, oss_endpoint, oss_bucket_name)


def compare_versions(version1: str, version2: str) -> int:
    """比较两个版本号
    Returns:
        -1 if version1 < version2
        0 if version1 == version2
        1 if version1 > version2
    """
    v1_parts = [int(x) for x in version1.split(".")]
    v2_parts = [int(x) for x in version2.split(".")]

    # 补齐长度
    max_len = max(len(v1_parts), len(v2_parts))
    v1_parts.extend([0] * (max_len - len(v1_parts)))
    v2_parts.extend([0] * (max_len - len(v2_parts)))

    for i in range(max_len):
        if v1_parts[i] < v2_parts[i]:
            return -1
        elif v1_parts[i] > v2_parts[i]:
            return 1
    return 0


@router.get("/updates/check", response=AppUpdateCheckOut)
@api_schema
def check_update(request, version: str, platform: str):
    """检查更新（Tauri Updater格式）

    此接口符合Tauri Updater API规范，可以直接配置到tauri.conf.json中
    """
    try:
        # 查找该平台的最新激活版本
        latest_update = (
            AppUpdate.objects.filter(platform=platform, is_active=True)
            .order_by("-published_at")
            .first()
        )

        if not latest_update:
            raise HttpError(404, f"No update available for platform: {platform}")

        # 比较版本号
        if compare_versions(version, latest_update.version) >= 0:
            raise HttpError(404, "Already up to date")

        # 检查是否需要强制更新
        if (
            latest_update.min_version
            and compare_versions(version, latest_update.min_version) < 0
        ):
            # 客户端版本低于最低支持版本，需要强制更新
            pass

        # 转换为Tauri格式
        return latest_update.to_tauri_format()

    except HttpError:
        raise
    except Exception as e:
        logger.error(f"检查更新失败: {e}", exc_info=True)
        raise HttpError(500, f"Failed to check update: {str(e)}") from e


@router.post("/updates", response=AppUpdateOut)
@api_schema
def create_update(
    request,
    payload: AppUpdateIn,
    file: UploadedFile | None = None,
):
    """创建应用更新版本（公开接口）
    
    支持两种请求方式：
    1. 纯 JSON 请求（application/json）：直接发送 AppUpdateIn 数据，file 参数为 None
    2. 文件上传请求（multipart/form-data）：包含文件时，Django Ninja 会自动处理
    """
    try:
        # 检查版本是否已存在
        if AppUpdate.objects.filter(
            version=payload.version, platform=payload.platform
        ).exists():
            raise HttpError(
                400, f"Version {payload.version} for {payload.platform} already exists"
            )

        # 如果提供了文件，上传到OSS
        download_url = payload.download_url
        file_size = payload.file_size

        if file:
            if file.size and file.size > 500 * 1024 * 1024:  # 500MB限制
                raise HttpError(400, "File size should not exceed 500MB")

            # 上传到OSS
            oss_object_key = f"updates/{payload.platform}/{payload.version}/{file.name}"
            file_content = file.read()
            bucket.put_object(oss_object_key, file_content)

            download_url = f"https://{oss_bucket_name}.{oss_endpoint}/{oss_object_key}"
            file_size = file.size

        # 创建更新记录
        update = AppUpdate(**payload.dict())
        update.download_url = download_url
        update.file_size = file_size
        update.save()

        logger.info(f"创建应用更新: {update.platform} {update.version}")
        return update
    except HttpError:
        raise
    except Exception as e:
        logger.error(f"创建应用更新失败: {e}", exc_info=True)
        raise HttpError(500, f"Failed to create update: {str(e)}") from e


@router.get("/updates", response=list[AppUpdateOut])
@api_paginate
def list_updates(
    request,
    platform: str | None = None,
    is_active: bool | None = None,
    keywords: str | None = None,
):
    """获取更新版本列表（公开接口）"""

    updates = AppUpdate.objects.all()

    if platform:
        updates = updates.filter(platform=platform)

    if is_active is not None:
        updates = updates.filter(is_active=is_active)

    if keywords:
        updates = updates.filter(
            Q(version__icontains=keywords) | Q(release_notes__icontains=keywords)
        )

    return updates.order_by("-published_at")


@router.get("/updates/{update_id}", response=AppUpdateOut)
@api_schema
def get_update(request, update_id: int):
    """获取更新版本详情（公开接口）"""

    return get_object_or_404(AppUpdate, id=update_id)


@router.put("/updates/{update_id}", response=AppUpdateOut)
@api_schema
def update_update(request, update_id: int, payload: AppUpdateIn):
    """更新应用更新版本信息（公开接口）"""

    update = get_object_or_404(AppUpdate, id=update_id)

    # 检查版本号是否冲突（如果版本号或平台改变了）
    if update.version != payload.version or update.platform != payload.platform:
        if (
            AppUpdate.objects.filter(version=payload.version, platform=payload.platform)
            .exclude(id=update_id)
            .exists()
        ):
            raise HttpError(
                400, f"Version {payload.version} for {payload.platform} already exists"
            )

    # 更新字段
    for field, value in payload.dict().items():
        setattr(update, field, value)

    update.save()
    logger.info(f"更新应用更新: {update.platform} {update.version}")
    return update


@router.delete("/updates/{update_id}", response=str)
@api_schema
def delete_update(request, update_id: int):
    """删除应用更新版本（公开接口）"""

    update = get_object_or_404(AppUpdate, id=update_id)
    update.delete()
    logger.info(f"删除应用更新: {update.platform} {update.version}")
    return "Ok"


@router.post("/updates/log", response=UpdateLogOut)
@api_schema
def create_update_log(request, payload: UpdateLogIn):
    """记录更新日志（客户端调用）"""

    # 获取客户端IP
    client_ip = None
    if hasattr(request, "META"):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            client_ip = x_forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.META.get("REMOTE_ADDR")

    # 创建日志记录
    log = UpdateLog(**payload.dict())
    log.client_ip = client_ip

    # 如果状态是成功或失败，设置完成时间
    if payload.status in ["success", "failed", "cancelled"]:
        log.completed_at = timezone.now()

    log.save()
    logger.info(
        f"记录更新日志: {payload.client_version} -> {payload.target_version} ({payload.status})"
    )
    return log


@router.get("/updates/log", response=list[UpdateLogOut])
@api_paginate
def list_update_logs(
    request,
    platform: str | None = None,
    status: str | None = None,
    keywords: str | None = None,
):
    """获取更新日志列表（公开接口）"""

    logs = UpdateLog.objects.all()

    if platform:
        logs = logs.filter(platform=platform)

    if status:
        logs = logs.filter(status=status)

    if keywords:
        logs = logs.filter(
            Q(client_version__icontains=keywords)
            | Q(target_version__icontains=keywords)
            | Q(error_message__icontains=keywords)
        )

    return logs.order_by("-created_at")


@router.get("/updates/log/{log_id}", response=UpdateLogOut)
@api_schema
def get_update_log(request, log_id: int):
    """获取更新日志详情（公开接口）"""

    return get_object_or_404(UpdateLog, id=log_id)
