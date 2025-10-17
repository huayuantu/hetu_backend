import base64
import io
import json
from functools import wraps
from typing import Any

import requests
from django.conf import settings
from django.core.cache import cache
from PIL import Image


def with_cache(
    cache_time: int = 60 * 60,
    device_id="ivm",
    channel_id: str | None = None,
    stream: str | None = None,
    quality: str | None = None,
    action: str | None = None,
):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key0 = kwargs.get("device_id", device_id)
            key1 = kwargs.get("channel_id", channel_id)
            key2 = kwargs.get("action", action)
            key3 = kwargs.get("stream", stream)
            key4 = kwargs.get("quality", quality)

            cache_key = f"ivm_{key0}_{key1}_{key2}_{key3}_{key4}"
            cached_data = cache.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
            else:
                result = func(*args, **kwargs)
                cache.set(
                    cache_key, json.dumps(result), timeout=cache_time
                )  # 设置缓存时间
                return result

        return wrapper

    return decorator


def compress_base64_image(base64_data: str, quality: int = 10) -> str:
    """
    压缩base64图片数据

    Args:
        base64_data: base64编码的图片数据
        quality: JPEG压缩质量（1-100），默认60

    Returns:
        压缩后的base64图片数据
    """
    try:
        # 解码base64数据
        image_data = base64.b64decode(base64_data)

        # 打开图片
        image = Image.open(io.BytesIO(image_data))

        # 转换为RGB模式（如果是RGBA等其他模式）
        if image.mode != 'RGB':
            image = image.convert('RGB')

        # 创建内存缓冲区
        buffer = io.BytesIO()

        # 保存为JPEG格式，指定压缩质量
        image.save(buffer, format='JPEG', quality=quality, optimize=True)

        # 编码为base64
        buffer.seek(0)
        compressed_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

        return compressed_base64

    except Exception as e:
        print(f"图片压缩失败: {e}")
        # 如果压缩失败，返回原始数据
        return base64_data


def handle_ivm_response(resp: requests.Response, operation: str) -> dict[str, Any]:
    """
    统一的IVM API响应处理函数

    Args:
        resp: HTTP响应对象
        operation: 操作名称，用于错误信息

    Returns:
        解析后的JSON响应数据

    Raises:
        Exception: 当HTTP状态码不是200或API返回业务错误时
    """
    # 检查HTTP状态码
    if resp.status_code != 200:
        raise Exception(f"获取{operation}失败: HTTP {resp.status_code} - {resp.text}")

    # 解析JSON响应
    try:
        resp_json = resp.json()
    except ValueError as e:
        raise Exception(f"获取{operation}失败: 无效的JSON响应 - {str(e)}") from e

    # 检查IVM业务错误码
    if resp_json.get("error_code"):
        error_msg = resp_json.get("error_message", "未知错误")
        raise Exception(f"获取{operation}失败: {resp_json['error_code']} {error_msg}")

    return resp_json


@with_cache(cache_time=60 * 60 * 24 * 6)  # 6天缓存，IVM token有效期7天
def get_access_token() -> str:
    """获取IVM访问TOKEN"""

    base_url = settings.IVM_BASE_URL
    user_id = settings.IVM_USER_ID
    access_key = settings.IVM_ACCESS_KEY
    secret_key = settings.IVM_SECRET_KEY

    url = f"{base_url}/v2/{user_id}/enterprises/access-token"

    headers = {
        "Content-Type": "application/json",
    }

    payload = {"ak": access_key, "sk": secret_key, "force_update": True}

    resp = requests.post(url, headers=headers, json=payload, timeout=10)
    resp_json = handle_ivm_response(resp, "访问TOKEN")

    return resp_json["access_token"]


@with_cache(30, action="capture")
def get_capture_url(device_id: str, channel_id: str = "1") -> str:
    """获取IVM设备截图"""

    base_url = settings.IVM_BASE_URL
    user_id = settings.IVM_USER_ID
    token = get_access_token()

    url = f"{base_url}/v1/{user_id}/devices/snap"
    params = {
        "device_id": device_id,
        "channel_id": channel_id,
        "storage": "false",
    }

    headers = {
        "Access-Token": token,
    }

    resp = requests.get(url, headers=headers, params=params, timeout=10)

    resp_json = handle_ivm_response(resp, "设备截图")

    # 压缩图片数据
    compressed_data = compress_base64_image(resp_json['pic_data'])

    return f"data:image/jpeg;base64,{compressed_data}"


@with_cache(60 * 60, action="video")
def get_video_url(
    device_id: str,
    channel_id: str = "1",
    protocol: str = "HTTPS_HLS",
    stream: str = "PRIMARY_STREAM",
) -> str:
    """获取IVM视频播放地址"""

    base_url = settings.IVM_BASE_URL
    user_id = settings.IVM_USER_ID
    token = get_access_token()

    url = f"{base_url}/v2/{user_id}/devices/channels/media/live-connections"

    headers = {
        "Content-Type": "application/json",
        "Access-Token": token,
    }

    payload = {
        "channels": [
            {
                "device_id": device_id,
                "channel_id": channel_id,
                "live_protocol": protocol,
                "stream_type": stream,
            }
        ],
        "use_times": 1,
        "expire_time": 3600,  # 1小时，和缓存时间匹配，用户偶尔打开查看
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=15)
    resp_json = handle_ivm_response(resp, "视频播放地址")

    # 检查是否有失败的连接
    if resp_json.get("fail_num", 0) > 0:
        raise Exception(f"获取视频地址失败: {resp_json.get('fail_num')} 个通道连接失败")

    # 返回第一个通道的播放地址
    return resp_json["live_connections"][0]["cloud_trans_connections"]["live_url"]


if __name__ == "__main__":
    import os
    import sys

    import django

    # 添加项目路径到sys.path
    project_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
    sys.path.insert(0, project_root)

    # 设置Django环境
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()

    # 测试函数
    def test_ivm_methods():
        print("🚀 开始测试IVM方法...")

        try:
            # 测试获取访问token
            print("\n1. 测试获取访问TOKEN...")
            token = get_access_token()
            print(f"✅ 访问TOKEN获取成功: {token[:20]}...")

            # 注意：这里需要使用实际的device_id，从.env文件读取测试用的设备ID
            import os

            device_id = os.getenv(
                "IVM_TEST_DEVICE_ID", "2102414366LDR4800076"
            )  # 从环境变量读取，默认使用示例值

            # 也可以测试其他设备ID来验证不同情况
            # device_id = "YOUR_DEVICE_ID"  # 替换为你要测试的设备ID

            # 测试不同通道的截图服务
            print("\n2. 测试截图服务（不同通道）...")

            # 测试channel_id="0"（可能已开通）
            print("   测试通道 0...")
            try:
                capture_url = get_capture_url(device_id=device_id, channel_id="0")
                print(f"   ✅ 通道0截图获取成功: {capture_url[:50]}...")
            except Exception as e:
                print(f"   ❌ 通道0截图获取失败: {e}")

            # 测试channel_id="1"（没有开通服务）
            print("   测试通道 1...")
            try:
                capture_url = get_capture_url(device_id=device_id, channel_id="1")
            except Exception as e:
                print(f"   ✅ 通道1截图获取失败（可能未开通）: {e}")

            # 测试获取视频URL
            print("\n3. 测试获取视频URL...")
            try:
                video_url = get_video_url(device_id=device_id, channel_id="1")
                print(f"✅ 视频URL获取成功: {video_url[:50]}...")
            except Exception as e:
                print(f"⚠️  视频URL获取失败: {e}")

            # 测试边界情况
            print("\n4. 测试边界情况...")

            # 测试不存在的设备
            print("   测试不存在设备...")
            fake_device_id = "NONEXISTENT_DEVICE_123"
            try:
                capture_url = get_capture_url(device_id=fake_device_id, channel_id="0")
                print(f"   ⚠️  返回结果（可能为默认图片）: {capture_url[:30]}...")
            except Exception as e:
                print(f"   ✅ 正确处理错误: {e}")

            # 测试无效的通道号
            print("   测试无效通道号...")
            try:
                capture_url = get_capture_url(device_id=device_id, channel_id="999")
                print(f"   ⚠️  返回结果: {capture_url[:30]}...")
            except Exception as e:
                print(f"   ✅ 正确处理错误: {e}")

            print("\n🎉 IVM方法测试完成！")
            print("💡 提示: 如果某些测试显示'意外成功'，可能是API返回了默认数据")
            print("   你可以检查返回的图片数据是否为有效的设备截图")

        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback

            traceback.print_exc()

    # 运行测试
    test_ivm_methods()
