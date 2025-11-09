from datetime import datetime

from ninja import Schema


class AppUpdateBase(Schema):
    """应用更新基础结构"""

    version: str
    platform: str
    download_url: str
    signature: str
    release_notes: str = ""
    is_active: bool = True
    file_size: int = 0
    force_update: bool = False
    min_version: str | None = None


class AppUpdateIn(AppUpdateBase):
    """创建应用更新输入结构"""

    pass


class AppUpdateOut(AppUpdateBase):
    """应用更新输出结构"""

    id: int
    published_at: datetime


class AppUpdateCheckIn(Schema):
    """更新检查输入结构"""

    version: str  # 当前版本号
    platform: str  # 平台类型: windows/macos/linux


class AppUpdateCheckOut(Schema):
    """更新检查输出结构（Tauri格式）"""

    version: str
    notes: str
    pub_date: str  # ISO格式日期字符串
    platforms: dict[str, dict[str, str]]  # {"windows": {"signature": "...", "url": "..."}}


class UpdateLogIn(Schema):
    """更新日志输入结构"""

    client_version: str
    target_version: str
    platform: str
    status: str  # checking/downloading/installing/success/failed/cancelled
    error_message: str | None = None
    meta: dict | None = None


class UpdateLogOut(Schema):
    """更新日志输出结构"""

    id: int
    client_version: str
    target_version: str
    platform: str
    status: str
    error_message: str | None
    client_ip: str | None
    created_at: datetime
    completed_at: datetime | None
    meta: dict | None

