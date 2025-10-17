import json
from functools import wraps
from typing import Any

import requests
from django.conf import settings
from django.core.cache import cache


def with_cache(
    cache_time: int = 60 * 60,
    device_id="ys",
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

            cache_key = f"ys_{key0}_{key1}_{key2}_{key3}_{key4}"
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


def handle_ys_response(resp: requests.Response, operation: str) -> dict[str, Any]:
    """统一处理萤石云API响应和错误"""
    # 检查HTTP状态码
    if resp.status_code != 200:
        raise Exception(f"获取{operation}失败: HTTP {resp.status_code} - {resp.text}")

    # 解析JSON响应
    try:
        resp_json = resp.json()
    except ValueError as e:
        raise Exception(f"获取{operation}失败: 无效的JSON响应 - {str(e)}") from e

    # 检查萤石云务错误码
    if resp_json.get("code") != "200":
        error_msg = resp_json.get("msg", "未知错误")
        raise Exception(f"获取{operation}失败: {resp_json['code']} {error_msg}")

    return resp_json


@with_cache(cache_time=60 * 60 * 24)
def get_access_token() -> str:
    """获取访问TOKEN"""

    app_key = settings.YS_APPKEY
    app_secret = settings.YS_APPSECRET
    url = f"https://open.ys7.com/api/lapp/token/get?appKey={app_key}&appSecret={app_secret}"
    headers = {
        "Accept": "*/*",
        "Connection": "keep-alive",
    }

    resp = requests.request("POST", url, headers=headers, data={}, timeout=5)
    resp_json = handle_ys_response(resp, "访问TOKEN")

    return resp_json["data"]["accessToken"]


@with_cache(60, action="capture")
def get_capture_url(
    device_id: str = "", channel_id: str = "1", quality: str = "3"
) -> str:
    """获取通道截图"""

    url = "https://open.ys7.com/api/lapp/device/capture"
    token = get_access_token()

    payload = f"accessToken={token}&deviceSerial={device_id}&channelNo={channel_id}&quality={quality}"
    headers = {
        "Accept": "*/*",
        "Connection": "keep-alive",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    resp = requests.request("POST", url, headers=headers, data=payload, timeout=5)
    resp_json = handle_ys_response(resp, "通道截图")

    return resp_json["data"]["picUrl"]


@with_cache(60 * 60, action="video")
def get_video_url(
    device_id: str = "",
    channel_id: str = "1",
    protocol: str = "1",
    stream: str | None = None,
) -> str:
    """获取视频播放地址"""

    url = "https://open.ys7.com/api/lapp/v2/live/address/get"
    token = get_access_token()

    payload = f"accessToken={token}&deviceSerial={device_id}&channelNo={channel_id}&expireTime=604800&protocol={protocol}"
    headers = {
        "Connection": "keep-alive",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    resp = requests.request("POST", url, headers=headers, data=payload)
    resp_json = handle_ys_response(resp, "视频播放地址")

    return resp_json["data"]["url"]


# 测试代码（仅在直接运行此文件时执行）
if __name__ == "__main__":
    import os
    import sys
    from pathlib import Path

    import django

    # 获取项目根目录
    project_root = Path(__file__).parent.parent.parent.parent
    sys.path.insert(0, str(project_root))

    # 设置Django环境
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()

    # 测试函数
    def test_ys_methods():
        print("🚀 开始测试萤石云方法...")

        try:
            # 测试获取访问token
            print("\n1. 测试获取访问TOKEN...")
            token = get_access_token()
            print(f"✅ 访问TOKEN获取成功: {token[:20]}...")

            # 注意：这里需要使用实际的device_id，你需要替换为有效的设备ID
            # 你可以从萤石云控制台获取有效的设备序列号
            device_id = os.getenv("YS_TEST_DEVICE_ID", "G32593002")

            # 测试获取截图
            print("\n2. 测试获取设备截图...")
            try:
                capture_url = get_capture_url(device_id=device_id, channel_id="1", quality="3")
                print(f"✅ 截图URL获取成功: {capture_url[:50]}...")
            except Exception as e:
                print(f"❌ 截图获取失败: {e}")

            # 测试获取视频URL
            print("\n3. 测试获取视频播放地址...")
            try:
                video_url = get_video_url(device_id=device_id, channel_id="1", protocol="1")
                print(f"✅ 视频URL获取成功: {video_url[:50]}...")
            except Exception as e:
                print(f"❌ 视频URL获取失败: {e}")

            # 测试边界情况
            print("\n4. 测试边界情况...")

            # 测试不存在的设备
            print("   测试不存在设备...")
            fake_device_id = "NONEXISTENT_DEVICE_123"
            try:
                capture_url = get_capture_url(device_id=fake_device_id, channel_id="1")
                print(f"   ⚠️  返回结果: {capture_url[:30]}...")
            except Exception as e:
                print(f"   ✅ 正确处理错误: {e}")

            # 测试无效的通道号
            print("   测试无效通道号...")
            try:
                capture_url = get_capture_url(device_id=device_id, channel_id="999")
                print(f"   ⚠️  返回结果: {capture_url[:30]}...")
            except Exception as e:
                print(f"   ✅ 正确处理错误: {e}")

            print("\n🎉 萤石云方法测试完成！")
            print("💡 提示: 请确保使用有效的设备ID进行测试")
            print("   你可以从萤石云控制台获取设备序列号")

        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()

    # 运行测试
    test_ys_methods()
