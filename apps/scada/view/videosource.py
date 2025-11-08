import logging
import threading

from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Router

from apps.scada.models import SiteVideoSource
from apps.scada.schema.videosource import (
    SiteVideoSourceIn,
    SiteVideoSourceOptionOut,
    SiteVideoSourceOut,
)
from apps.scada.utils.ivm import (
    get_access_token as ivm_get_access_token,
)
from apps.scada.utils.ivm import (
    get_capture_url as ivm_get_capture_url,
)
from apps.scada.utils.ivm import (
    get_video_url as ivm_get_video_url,
)
from apps.scada.utils.ys import (
    get_access_token,
)
from apps.scada.utils.ys import (
    get_capture_url as ys_get_capture_url,
)
from apps.scada.utils.ys import (
    get_video_url as ys_get_video_url,
)
from apps.sys.utils import AuthBearer
from utils.schema.base import api_schema

router = Router()
logger = logging.getLogger(__name__)


def update_capture_async(video_id: int, source_type: str, device_id: str, channel: str):
    """异步更新视频源的截图数据"""
    try:
        # 获取新的截图
        new_capture = None
        if source_type == "YS":
            new_capture = ys_get_capture_url(
                device_id=device_id, channel_id=int(channel)
            )
        elif source_type == "VIM":
            new_capture = ivm_get_capture_url(
                device_id=device_id, channel_id=channel
            )

        # 更新数据库中的capture字段和时间戳
        if new_capture:
            SiteVideoSource.objects.filter(id=video_id).update(
                capture=new_capture,
                capture_updated_at=timezone.now()
            )
            logger.info(f"视频源 {video_id} 的截图已更新")
        else:
            logger.warning(f"视频源 {video_id} 获取截图失败，返回为空")
    except Exception as e:
        logger.error(f"更新视频源 {video_id} 截图失败: {e}", exc_info=True)


@router.post(
    "/{site_id}/videosource",
    response=SiteVideoSourceOptionOut,
    auth=AuthBearer(
        [
            ("scada:site:add", "x"),
            ("scada:site:permit:{site_id}", "w"),
        ]
    ),
)
@api_schema
def create_videosource(request, site_id: int, payload: SiteVideoSourceIn):
    """给站点添加视频源"""

    svs = SiteVideoSource(site_id=site_id, **payload.dict())
    svs.save()
    return svs


@router.get(
    "/{site_id}/videosource",
    response=list[SiteVideoSourceOptionOut],
    auth=AuthBearer(
        [
            ("scada:site:edit", "x"),
            ("scada:site:permit:{site_id}", "r"),
        ]
    ),
)
@api_schema
def list_videosource(request, site_id: int):
    """列出视频源"""

    return SiteVideoSource.objects.filter(site_id=site_id).all()  # type: ignore[attr-defined]


@router.get(
    "/{site_id}/videosource/{videosource_id}",
    response=SiteVideoSourceOut,
    auth=AuthBearer(
        [
            ("scada:site:edit", "x"),
            ("scada:site:permit:{site_id}", "r"),
        ]
    ),
)
@api_schema
def get_videosource(request, videosource_id: int, site_id: int):
    """调用视频源接口获取播放地址和截图"""

    video = get_object_or_404(SiteVideoSource, id=videosource_id, site_id=site_id)
    output = SiteVideoSourceOut.from_orm(video)

    # 先返回数据库中已存储的截图（如果有的话）
    if video.capture:
        output.capture = video.capture

    # 检查是否需要更新截图（避免频繁更新）
    if video.should_update_capture():
        # 启动后台线程异步更新截图
        thread = threading.Thread(
            target=update_capture_async,
            args=(video.id, video.source_type, video.device_id, video.channel)
        )
        thread.daemon = True
        thread.start()
    else:
        logger.debug(
            f"视频源 {video.id} 截图更新间隔未到，跳过更新。"
            f"上次更新: {video.capture_updated_at}"
        )

    # 根据视频源类型选择对应的API调用获取视频地址和token
    if video.source_type == "YS":
        # 萤石云API
        try:
            output.video_source = ys_get_video_url(
                device_id=video.device_id, channel_id=int(video.channel)
            )
            output.token = get_access_token()
        except Exception as e:
            logger.error(f"获取萤石云视频地址或Token错误: {e}", exc_info=True)

    elif video.source_type == "VIM":
        # 华为IVM API
        try:
            output.video_source = ivm_get_video_url(
                device_id=video.device_id, channel_id=video.channel
            )
            output.token = ivm_get_access_token()
        except Exception as e:
            logger.error(f"获取华为IVM视频地址或Token错误: {e}", exc_info=True)
    else:
        # 不支持的视频源类型
        logger.warning(f"不支持的视频源类型: {video.source_type}")

    return output


@router.delete(
    "/{site_id}/videosource/{videosource_id}",
    response=str,
    auth=AuthBearer(
        [
            ("scada:site:delete", "x"),
            ("scada:site:permit:{site_id}", "w"),
        ]
    ),
)
@api_schema
def delete_videosource(request, site_id: int, videosource_id: int):
    """删除通道"""

    svs = get_object_or_404(SiteVideoSource, id=videosource_id, site_id=site_id)
    svs.delete()
    return "Ok"
