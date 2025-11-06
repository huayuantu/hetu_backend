from ninja import Schema


class VariableBase(Schema):
    """变量基础结构"""

    # 变量名
    name: str
    # 变量组
    group: str
    # 变量类型 I/F/B
    type: str
    # 变量读写
    rw: bool = False
    # 脉冲或电平信号
    pulse: bool = False
    # 是否本地
    local: bool = False
    # 自定义描述
    details: str = ""


class VariableOut(VariableBase):
    """变量返回结构"""

    # 内部ID
    id: int
    # 变量模块
    module_id: int
    # 站点
    site_id: int


class VariableGroupOut(Schema):
    """变量组返回结构"""

    group: str


class VariableOptionOut(Schema):
    """选项列表结构"""

    # 内部ID
    id: int
    # 变量名
    name: str
    # 变量组
    group: str
    # 变量类型 I/F/B
    type: str
    # 变量读写
    rw: bool = False


class VariableIn(VariableBase):
    """创建变量请求结构"""

    pass


class VariableUpdateIn(Schema):
    """更新请求结构"""

    # 变量类型 I/F/B
    type: str
    # 变量读写
    rw: bool = False
    # 脉冲或电平信号
    pulse: bool = False
    # 自定义描述
    details: str


class ReadValueIn(Schema):
    """批量读取请求"""

    variable_ids: list[int] = []


class ReadValueOut(Schema):
    """变量值结构体"""

    class Value(Schema):
        # 时间搓
        timestamp: int
        # 值
        value: float

    # 变量ID
    id: int
    # 列表值
    values: list[Value] = []
    # 错误状态
    error: int = 0


class WriteValueIn(Schema):
    """写模块变量请求参数"""

    # 变量ID
    id: int
    # 写入值
    value: float


class WriteValueOut(Schema):
    """写模块变量响应参数"""

    # 变量ID
    id: int
    # 写入结果
    error: int = 0


class QueryRangeIn(Schema):
    """批量变量历史数据查询请求结构"""

    # 变量ID列表
    variable_ids: list[int]
    # 开始时间（Unix时间戳，秒）
    start_time: int
    # 结束时间（Unix时间戳，秒）
    end_time: int
    # 步长（秒），默认60
    step: int = 60
    # 聚合方式：'avg' | 'min' | 'max' | None，默认None（不聚合）
    aggregation: str = None
