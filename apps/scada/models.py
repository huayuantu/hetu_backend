from django.db import models


class Site(models.Model):
    """站点模型"""

    # 站点名称
    name = models.CharField(max_length=255, unique=True)
    # 联系人姓名
    contact = models.CharField(max_length=255)
    # 联系人手机号码
    mobile = models.CharField(max_length=255)
    # 站点状态，可以是整数或其他适当的数据类型
    status = models.IntegerField(default=1)
    # 经度
    longitude = models.FloatField(default=114.305215)
    # 纬度
    latitude = models.FloatField(default=30.592849)
    # 记录站点信息创建的日期和时间
    create_time = models.DateTimeField(auto_now_add=True)
    # 备注信息，可以为空
    remark = models.CharField(max_length=255, null=True)


class Module(models.Model):
    """数据模块模型"""

    # 管理端名称
    name = models.CharField(max_length=255, unique=True)
    # 巨控模块账号
    module_number = models.CharField(max_length=255, unique=True)
    # 密钥
    module_secret = models.CharField(max_length=255)
    # 巨控模块地址
    module_url = models.CharField(max_length=255)
    # 修改日期
    updated_at = models.DateTimeField(auto_now=True, auto_created=True)
    # 所属站点
    site = models.ForeignKey(Site, on_delete=models.PROTECT, null=True)

    def __str__(self) -> str:
        return f"Module: {self.name}"


class Variable(models.Model):
    """数据模块变量模型"""

    # 变量名
    name = models.CharField(max_length=255)
    # 变量类型
    type = models.CharField(max_length=255)
    # 变量组
    group = models.CharField(max_length=255, db_index=True, default="")
    # 变量读写权限
    rw = models.BooleanField(default=False)
    # 脉冲或电平信号（写入变量有效）
    pulse = models.BooleanField(default=False)
    # 是否本地变量
    local = models.BooleanField(default=False)
    # 变量自定义描述
    details = models.CharField(default="", max_length=255)
    # 所属模块
    module = models.ForeignKey(Module, on_delete=models.PROTECT)

    def __str__(self) -> str:
        return f"Module: {self.module.name}, Var: {self.name}"

    class Meta:
        unique_together = ("name", "module")


class Rule(models.Model):
    """警告规则结构"""

    # 变量
    variable = models.ForeignKey(Variable, on_delete=models.PROTECT)
    # 规则名称
    name = models.CharField(max_length=255)
    # 描述
    description = models.TextField()
    # 规则类型
    alert_type = models.CharField(max_length=255)
    # 警告类型
    alert_level = models.CharField(max_length=255, default="none")
    # 阈值
    threshold = models.FloatField(default=0.0)
    # 状态值
    state = models.IntegerField(default=0)
    # 权重
    weight = models.FloatField(default=1.0)
    # 持续时间
    duration = models.CharField(max_length=20, default="0s")

    class Meta:
        # 定义联合唯一约束
        unique_together = ("name", "variable")

    def __str__(self):
        return self.name


# 通知等级
LEVEL_CHOICES = (
    ("default", "默认"),
    ("info", "信息"),
    ("warning", "警告"),
    ("error", "错误"),
    ("critical", "严重"),
)


class Notify(models.Model):
    """通知消息模型"""

    # 外部的ID标识，表示是否属于同一个事件
    external_id = models.CharField(max_length=255, db_index=True)
    # 通知等级
    level = models.CharField(max_length=255, choices=LEVEL_CHOICES)
    # 标题
    title = models.CharField(max_length=255, db_index=True)
    # 内容字段
    content = models.TextField()
    # 消息来源
    source = models.CharField(max_length=255)
    # 事情发生的时间
    notified_at = models.DateTimeField(db_index=True)
    # 记录消息的时间
    created_at = models.DateTimeField(auto_now_add=True)
    # 是否已确认
    ack = models.BooleanField(default=False)
    # 确认时间，允许为空
    ack_at = models.DateTimeField(null=True)
    # 元数据，使用 JSONField 存储
    meta = models.JSONField(null=True)

    def __str__(self):
        return f"{self.title} ({self.level})"


class Graph(models.Model):
    """组态图模型"""

    # 组态名称
    name = models.CharField(max_length=255, unique=True)
    # 状态字段，用于表示站点配置的状态
    status = models.IntegerField()
    # 记录站点配置信息创建的日期和时间
    create_time = models.DateTimeField(auto_now_add=True)
    # JSON 字段，用于存储绘图相关的配置数据
    data = models.TextField()
    # 备注信息，可以为空
    remark = models.CharField(max_length=255, null=True)
    # 排序
    order = models.IntegerField(default=1)
    # 站点
    site = models.ForeignKey(Site, on_delete=models.PROTECT)

    def __str__(self):
        return self.name


class Collector(models.Model):
    """采集器模型"""

    # 采集器对应模块
    module = models.OneToOneField(Module, on_delete=models.PROTECT)
    # 采集间隔
    interval = models.IntegerField(default=5)
    # 请求超时
    timeout = models.IntegerField(default=3)


STATIC_METHOD = (
    ("sum", "求和"),
    ("avg", "平均"),
)


class SiteStatistic(models.Model):
    """站点统计对象"""

    # 统计量名称
    name = models.CharField(max_length=255)
    # 统计方法
    method = models.CharField(max_length=255, choices=LEVEL_CHOICES)
    # 统计对象
    variables = models.ManyToManyField(Variable)
    # 所属站点
    site = models.ForeignKey(Site, on_delete=models.PROTECT)

    class Meta:
        unique_together = [["name", "site"]]


VideoSourceType = (
    ("YS", "萤石"),
    ("VIM", "华为行业视频"),
)


class SiteVideoSource(models.Model):
    """站点监控视频源"""

    # 设备ID
    device_id = models.CharField(max_length=255)
    # 设备类别
    device_type = models.CharField(max_length=255)
    # 设备通道
    channel = models.CharField(max_length=255)
    # 状态字段
    status = models.IntegerField(default=1)
    # 所属站点
    site = models.ForeignKey(Site, on_delete=models.PROTECT)
    # 视频源类别
    source_type = models.CharField(
        max_length=100, choices=VideoSourceType, default="YS"
    )
    # 截图Base64数据
    capture = models.TextField(null=True)
    # 截图最后更新时间
    capture_updated_at = models.DateTimeField(null=True)

    def should_update_capture(self, min_interval_seconds: int = 300) -> bool:
        """判断是否需要更新截图

        Args:
            min_interval_seconds: 最小更新间隔（秒），默认5分钟

        Returns:
            True表示需要更新，False表示不需要更新
        """
        if not self.capture_updated_at:
            return True
        from django.utils import timezone

        time_diff = (timezone.now() - self.capture_updated_at).total_seconds()
        return time_diff >= min_interval_seconds


# 平台类型选择
PLATFORM_CHOICES = (
    ("windows", "Windows"),
    ("macos", "macOS"),
    ("linux", "Linux"),
)


class AppUpdate(models.Model):
    """应用更新版本模型"""

    # 版本号，格式：major.minor.patch (例如: 1.0.0)
    version = models.CharField(max_length=50, unique=True, db_index=True)
    # 平台类型
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES, db_index=True)
    # 下载地址（OSS URL或CDN URL）
    download_url = models.URLField(max_length=500)
    # Tauri签名（用于验证更新包）
    signature = models.TextField()
    # 更新说明/发布日志
    release_notes = models.TextField(default="")
    # 发布时间
    published_at = models.DateTimeField(auto_now_add=True)
    # 是否激活（只有激活的版本才会被返回）
    is_active = models.BooleanField(default=True, db_index=True)
    # 文件大小（字节）
    file_size = models.BigIntegerField(default=0)
    # 是否强制更新
    force_update = models.BooleanField(default=False)
    # 最低支持版本（低于此版本的客户端必须更新）
    min_version = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        unique_together = [["version", "platform"]]
        ordering = ["-published_at"]

    def __str__(self):
        return f"{self.platform} {self.version}"

    def to_tauri_format(self) -> dict:
        """转换为Tauri Updater API格式"""
        return {
            "version": self.version,
            "notes": self.release_notes,
            "pub_date": self.published_at.isoformat() + "Z",
            "platforms": {
                self.platform: {
                    "signature": self.signature,
                    "url": self.download_url,
                }
            },
        }


class UpdateLog(models.Model):
    """更新日志模型（记录客户端更新行为）"""

    # 客户端版本
    client_version = models.CharField(max_length=50, db_index=True)
    # 目标版本（要更新到的版本）
    target_version = models.CharField(max_length=50, db_index=True)
    # 平台类型
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES, db_index=True)
    # 更新状态
    status = models.CharField(
        max_length=20,
        choices=(
            ("checking", "检查中"),
            ("downloading", "下载中"),
            ("installing", "安装中"),
            ("success", "成功"),
            ("failed", "失败"),
            ("cancelled", "取消"),
        ),
        db_index=True,
    )
    # 错误信息（如果失败）
    error_message = models.TextField(null=True, blank=True)
    # 客户端IP地址
    client_ip = models.GenericIPAddressField(null=True, blank=True)
    # 记录时间
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    # 完成时间
    completed_at = models.DateTimeField(null=True, blank=True)
    # 元数据（JSON格式，存储额外信息）
    meta = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.client_version} -> {self.target_version} ({self.status})"
