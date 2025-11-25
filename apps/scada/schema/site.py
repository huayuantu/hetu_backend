from datetime import datetime
from enum import Enum

from ninja import Schema
from pydantic import Field


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
    # 权限：r 表示只读，w 表示读写
    permit: str | None = None


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
    """Dashboard 卡片配置结构（输入，使用下划线命名）"""

    time_interval: str | None = None  # hour, day, week, month
    aggregation: str | None = None  # avg, min, max, sum
    precision: int | None = None
    unit: str | None = None
    icon: str | None = None  # 图标名称（lucide-vue-next 图标名称）


class DashboardCardConfigOut(Schema):
    """Dashboard 卡片配置结构（输出，使用驼峰命名）"""

    time_interval: str | None = Field(None, alias="timeInterval")  # hour, day, week, month
    aggregation: str | None = None  # avg, min, max, sum
    precision: int | None = None
    unit: str | None = None
    icon: str | None = None  # 图标名称（lucide-vue-next 图标名称）

    class Config:
        populate_by_name = True  # 允许使用字段名或别名


class DashboardCardLayout(Schema):
    """Dashboard 卡片布局结构"""

    x: int | None = None
    y: int | None = None


class DashboardCardIn(Schema):
    """Dashboard 卡片创建/更新结构"""

    variable_id: int
    variable_name: str
    title: str = ""  # 卡片标题，默认为空（前端会使用变量名称作为默认值）
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
    title: str  # 卡片标题
    card_type: str
    config: DashboardCardConfigOut  # 配置信息（包含 icon 字段）
    position: int
    layout: dict | None = None
    created_at: datetime
    updated_at: datetime


class GlobalStatisticsOut(Schema):
    """全局统计数据返回结构"""

    total_site: int  # 接入站点数（过滤掉 connecting 状态的站点）
    total_variables: int  # 监控点数（所有站点的变量总数）
    total_water: float  # 处理总量（所有站点的"处理总量"统计值之和）
    total_warning: int  # 处理预警（激活的告警数 + 总告警数）
