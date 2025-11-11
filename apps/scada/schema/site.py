from datetime import datetime
from enum import Enum

from ninja import Schema


class SiteBase(Schema):
    """站点基本结构"""

    # 站点名称
    name: str
    # 联系人姓名
    contact: str
    # 联系人手机号码
    mobile: str
    # 站点状态，可以是整数或其他适当的数据类型
    status: int = 1
    # 备注信息，可以为空
    remark: str | None
    # 默认武汉市的经度
    longitude: float = 114.305215
    # 默认武汉市的纬度
    latitude: float = 30.592849


class SiteIn(SiteBase):
    """创建站点请求结构"""

    pass


class SiteOut(SiteBase):
    """站点返回结构"""

    # ID
    id: int
    # 创建时间
    create_time: datetime


class SiteOptionOut(Schema):
    """选项列表"""

    # ID
    id: int
    # 名称
    name: str
    # 站点状态
    status: int = 1
    # 默认武汉市的经度
    longitude: float = 114.305215
    # 默认武汉市的纬度
    latitude: float = 30.592849


class StaticMethod(str, Enum):
    """统计类型"""

    SUM = "sum"
    AVG = "avg"


class SiteStatisticBase(Schema):
    """统计对象基础结构"""

    # 统计名
    name: str
    # 统计类型
    method: StaticMethod = StaticMethod.SUM
    # 统计对象
    variable_ids: list[int] = []


class SiteStatisticIn(SiteStatisticBase):
    """统计对象创建结构"""

    pass


class SiteStatisticOut(SiteStatisticBase):
    """统计对象选项返回值"""

    # 编号
    id: int


class SiteStatisticValueOut(SiteStatisticOut):
    """统计对象返回结构"""

    # 统计值
    value: float = 0
    # 统计的时间戳
    timestamp: float = 0


class SitePermitType(str, Enum):
    """站点权限类型"""

    NONE = "none"
    READ = "r"
    WRITE = "w"


class SitePermit(Schema):
    """站点授权请求结构"""

    site_id: int
    user_id: int
    permit: SitePermitType


class SiteVariableCountOut(Schema):
    """站点变量计数结构"""
    
    site_id: int
    variable_count: int


class DashboardCardConfig(Schema):
    """Dashboard 卡片配置结构"""
    
    time_interval: str | None = None  # hour, day, week, month
    aggregation: str | None = None  # avg, min, max, sum
    precision: int | None = None
    unit: str | None = None


class DashboardCardLayout(Schema):
    """Dashboard 卡片布局结构"""
    
    x: int | None = None
    y: int | None = None


class DashboardCardIn(Schema):
    """Dashboard 卡片创建/更新结构"""
    
    variable_id: int
    variable_name: str
    card_type: str  # number, switch, line, bar
    config: DashboardCardConfig = DashboardCardConfig()
    position: int = 0
    layout: DashboardCardLayout | None = None


class DashboardCardOut(Schema):
    """Dashboard 卡片返回结构"""
    
    id: int
    site_id: int
    variable_id: int
    variable_name: str
    card_type: str
    config: dict
    position: int
    layout: dict | None = None
    created_at: datetime
    updated_at: datetime
