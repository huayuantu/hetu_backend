from django.db.models import Q, Count
from django.shortcuts import get_object_or_404
from ninja import Router
from ninja.errors import HttpError

from apps.scada.models import Site, SiteStatistic, DashboardCard
from apps.scada.schema.site import (
    SiteIn,
    SiteOptionOut,
    SiteOut,
    SitePermit,
    SitePermitType,
    SiteStatisticIn,
    SiteStatisticOut,
    SiteStatisticValueOut,
    SiteVariableCountOut,
    DashboardCardIn,
    DashboardCardOut,
)
from apps.scada.utils.promql import promql_query
from apps.sys.models import User
from apps.sys.utils import AuthBearer, get_enforcer
from utils.schema.base import api_schema
from utils.schema.paginate import api_paginate

router = Router()


@router.get(
    "/{site_id}/permit",
    response=list[SitePermit],
    auth=AuthBearer(
        [
            ("scada:site:edit", "x"),
            ("scada:site:info", "x"),
        ]
    ),
)
@api_schema
def get_permit_list(request, site_id: int):
    enforcer = get_enforcer()
    policies = enforcer.get_filtered_policy(1, f"scada:site:permit:{site_id}")
    permit: dict[int, str] = {}

    for username, _, permission in policies:
        user = User.objects.filter(username=username).values("id").first()
        if not user:
            continue
        user_id = user["id"]
        if permission == "w":
            permit[user_id] = permission
        elif permission == "r" and user_id not in permit:
            permit[user_id] = permission

    output = [
        SitePermit(user_id=user_id, permit=SitePermitType(permission), site_id=site_id)
        for user_id, permission in permit.items()
    ]

    return output


@router.get(
    "/permit/{user_id}",
    response=list[SitePermit],
    auth=AuthBearer(
        [
            ("scada:site:edit", "x"),
            ("scada:site:info", "x"),
        ]
    ),
)
@api_schema
def get_permit_by_user(request, user_id: int):
    """获取用户授权的列表"""

    user = get_object_or_404(User, id=user_id)
    enforcer = get_enforcer()
    policies = [
        policy
        for policy in enforcer.get_filtered_policy(0, user.username)
        if policy[1].startswith("scada:site:permit:")
    ]
    permit: dict[int, str] = {}

    for _, target, permission in policies:
        site_id = target.split(":")[-1]
        if permission == "w":
            permit[site_id] = permission
        elif permission == "r" and site_id not in permit:
            permit[site_id] = permission

    output = [
        SitePermit(user_id=user_id, permit=SitePermitType(permission), site_id=site_id)
        for site_id, permission in permit.items()
    ]

    return output


@router.post(
    "/{site_id}/permit",
    response=str,
    auth=AuthBearer(
        [
            ("scada:site:edit", "x"),
        ]
    ),
)
@api_schema
def grand_permits(request, site_id: int, payload: SitePermit):
    """站点权限"""

    enforcer = get_enforcer()
    user = get_object_or_404(User, id=payload.user_id)

    if payload.permit == SitePermitType.WRITE:
        enforcer.add_policy(user.username, f"scada:site:permit:{site_id}", "w")
        enforcer.add_policy(user.username, f"scada:site:permit:{site_id}", "r")
    elif payload.permit == SitePermitType.READ:
        enforcer.remove_filtered_policy(
            0, user.username, f"scada:site:permit:{site_id}"
        )
        enforcer.add_policy(user.username, f"scada:site:permit:{site_id}", "r")
    else:
        enforcer.remove_filtered_policy(
            0, user.username, f"scada:site:permit:{site_id}"
        )
    return "Ok"


@router.post(
    "",
    response=SiteOut,
    auth=AuthBearer(
        [
            ("scada:site:add", "x"),
        ]
    ),
)
@api_schema
def create_site(request, payload: SiteIn):
    """创建站点"""

    site = Site(**payload.dict())
    site.save()
    return site


@router.get(
    "options",
    response=list[SiteOptionOut],
    auth=AuthBearer(
        [
            ("scada:site:edit", "x"),
            ("scada:site:info", "x"),
        ],
    ),
)
@api_schema
def get_site_option_list(request):
    """选项列表"""

    # Note: permit filtering was disabled, returning all sites
    # enforcer = get_enforcer()
    # policies = enforcer.get_filtered_policy(0, request.auth["username"])
    # permit_ids = [
    #     int(policy[1].split(":")[-1])
    #     for policy in policies
    #     if policy[1].startswith("scada:site:permit:")
    # ]
    # return Site.objects.filter(id__in=permit_ids)
    return Site.objects.all()


@router.get(
    "",
    response=list[SiteOut],
    auth=AuthBearer(
        [
            ("scada:site:edit", "x"),
        ]
    ),
)
@api_paginate
def get_site_list(request, keywords: str = None):
    """获取信息列表, 不检查权限"""

    sites = Site.objects.all()

    if keywords:
        sites = sites.filter(
            Q(name__icontains=keywords) | Q(contact__icontains=keywords)
        )

    return sites


@router.get(
    "/{site_id}",
    response=SiteOut,
    auth=AuthBearer(
        [
            ("scada:site:edit", "x"),
            ("scada:site:info", "x"),
            ("scada:site:permit:{site_id}", "r"),
        ]
    ),
)
@api_schema
def get_site_info(request, site_id: int):
    """获取信息"""

    return get_object_or_404(Site, id=site_id)


@router.put(
    "/{site_id}",
    response=SiteOut,
    auth=AuthBearer(
        [
            ("scada:site:edit", "x"),
            ("scada:site:permit:{site_id}", "w"),
        ]
    ),
)
@api_schema
def update_site(request, site_id: int, payload: SiteIn):
    """修改信息"""

    site = get_object_or_404(Site, id=site_id)
    site.name = payload.name
    site.contact = payload.contact
    site.mobile = payload.mobile
    site.status = payload.status
    site.remark = payload.remark
    site.longitude = payload.longitude
    site.latitude = payload.latitude
    site.save()
    return site


@router.delete(
    "/{site_id}",
    response=str,
    auth=AuthBearer(
        [
            ("scada:site:delete", "x"),
            ("scada:site:permit:{site_id}", "w"),
        ]
    ),
)
@api_schema
def delete_site(request, site_id: int):
    """修改信息"""

    site = get_object_or_404(Site, id=site_id)
    site.delete()
    return "Ok"


@router.post(
    "/{site_id}/statistic",
    response=SiteStatisticOut,
    auth=AuthBearer(
        [
            ("scada:site:edit", "x"),
            ("scada:site:permit:{site_id}", "w"),
        ]
    ),
)
@api_schema
def create_statistic(request, site_id: int, payload: SiteStatisticIn):
    """创建站点统计变量"""

    # Verify site exists
    get_object_or_404(Site, id=site_id)
    statistic = SiteStatistic(
        site_id=site_id, **payload.dict(exclude={"variable_ids": True})
    )
    statistic.save()

    statistic.variables.set(payload.variable_ids)

    output = SiteStatisticOut.from_orm(statistic)
    output.variable_ids = [v.id for v in statistic.variables.all()]

    return output


@router.get(
    "/{site_id}/statistic",
    response=SiteStatisticValueOut,
    auth=AuthBearer(
        [
            ("scada:site:edit", "x"),
            ("scada:site:info", "x"),
        ]
    ),
)
@api_schema
def get_statistic_value(
    request, site_id: int, statistic_id: int = None, statistic_name: str = None
):
    """计算统计值并返回"""

    if statistic_id:
        statistic = get_object_or_404(SiteStatistic, id=statistic_id, site_id=site_id)
    elif statistic_name:
        statistic = SiteStatistic.objects.filter(
            site_id=site_id, name=statistic_name
        ).first()
        if not statistic:
            # 通过名字找不到统计量就直接返回0
            return SiteStatisticValueOut(id=-1, name=statistic_name)
    else:
        raise HttpError(400, "指定statistic_id或指定statistic_name")

    output = SiteStatisticValueOut.from_orm(statistic)

    # 获取所有变量，按模块分组以进行批量查询
    variables = statistic.variables.select_related("module").all()
    
    # 按模块分组变量
    from collections import defaultdict
    module_vars = defaultdict(list)
    for v in variables:
        output.variable_ids.append(v.id)
        module_vars[v.module.module_number].append(v)

    values = []
    timestamp = 0

    # 按模块批量查询 Prometheus
    for module_number, vars_list in module_vars.items():
        # 构建批量查询字符串：使用正则表达式匹配多个变量名
        var_names = [v.name for v in vars_list]
        query_str = "grm_" + module_number + "_gauge"
        query_str += '{name=~"' + "|".join(var_names) + '"}'

        try:
            query_data = promql_query(query_str)
        except Exception:
            continue

        # 从查询结果中提取值
        result_dict = {}
        for result in query_data.get("data", {}).get("result", []):
            metric_name = result.get("metric", {}).get("name")
            if metric_name:
                result_dict[metric_name] = result.get("value", [0, 0])

        # 匹配变量并累加值
        for v in vars_list:
            if v.name in result_dict:
                value_data = result_dict[v.name]
                timestamp = max(timestamp, int(value_data[0]))
                values.append(float(value_data[1]))

    # 目前只支持累加
    output.value = sum(values)
    output.timestamp = timestamp
    return output


@router.get(
    "/{site_id}/statistic/options",
    response=list[SiteStatisticOut],
    auth=AuthBearer(
        [
            ("scada:site:edit", "x"),
            ("scada:site:info", "x"),
            ("scada:site:permit:{site_id}", "r"),
        ]
    ),
)
@api_schema
def list_statistic(request, site_id: int):
    """获取列表"""
    statistic = SiteStatistic.objects.filter(site_id=site_id)
    outputs = []

    for s in statistic:
        o = SiteStatisticOut.from_orm(s)
        o.variable_ids = [v.id for v in s.variables.all()]
        outputs.append(o)

    return outputs


@router.put(
    "/{site_id}/statistic/{statistic_id}",
    response=SiteStatisticOut,
    auth=AuthBearer(
        [
            ("scada:site:edit", "x"),
            ("scada:site:permit:{site_id}", "w"),
        ]
    ),
)
@api_schema
def update_statistic(
    request, site_id: int, statistic_id: int, payload: SiteStatisticIn
):
    """更新统计值配置"""

    statistic = get_object_or_404(SiteStatistic, id=statistic_id, site_id=site_id)
    statistic.name = payload.name
    statistic.method = payload.method
    statistic.save()

    statistic.variables.set(payload.variable_ids)

    output = SiteStatisticOut.from_orm(statistic)
    output.variable_ids = [v.id for v in statistic.variables.all()]
    return output


@router.delete(
    "/{site_id}/statistic/{statistic_id}",
    response=str,
    auth=AuthBearer(
        [
            ("scada:site:edit", "x"),
            ("scada:site:permit:{site_id}", "w"),
        ]
    ),
)
@api_schema
def delete_statistic(request, site_id: int, statistic_id: int):
    """删除统计值"""

    statistic = get_object_or_404(SiteStatistic, id=statistic_id, site_id=site_id)
    statistic.delete()

    return "Ok"


@router.get(
    "/variables/count",
    response=list[SiteVariableCountOut],
    auth=AuthBearer(
        [
            ("scada:site:info", "x"),
        ]
    ),
)
@api_schema
def get_variables_count(request, site_ids: str = None):
    """批量获取多个站点的变量总数
    
    优化：使用一次查询获取所有站点的变量总数
    site_ids: 逗号分隔的站点ID列表，如 "1,2,3"。如果不提供，返回所有站点
    """
    from apps.scada.models import Variable
    from collections import defaultdict
    
    # 解析站点ID列表
    if site_ids:
        site_id_list = [int(sid.strip()) for sid in site_ids.split(',') if sid.strip()]
        if not site_id_list:
            return []
    else:
        # 如果没有提供站点ID，返回所有站点
        site_id_list = None
    
    # 使用一次查询获取所有站点的变量总数
    if site_id_list:
        variable_counts = (
            Variable.objects
            .filter(module__site_id__in=site_id_list)
            .values('module__site_id')
            .annotate(variable_count=Count('id'))
        )
    else:
        variable_counts = (
            Variable.objects
            .values('module__site_id')
            .annotate(variable_count=Count('id'))
        )
    
    # 按站点ID汇总
    site_counts = defaultdict(int)
    for item in variable_counts:
        site_id = item['module__site_id']
        count = item['variable_count']
        site_counts[site_id] += count
    
    # 构建返回结果
    result = []
    for site_id, count in site_counts.items():
        result.append(SiteVariableCountOut(
            site_id=site_id,
            variable_count=count
        ))
    
    return result


@router.get(
    "/{site_id}/dashboard/cards",
    response=list[DashboardCardOut],
    auth=AuthBearer(
        [
            ("scada:site:info", "x"),
            ("scada:site:permit:{site_id}", "r"),
        ]
    ),
)
@api_schema
def get_dashboard_cards(request, site_id: int):
    """获取站点的 Dashboard 卡片列表"""
    site = get_object_or_404(Site, id=site_id)
    cards = DashboardCard.objects.filter(site=site).order_by("position", "id")
    
    result = []
    for card in cards:
        result.append(DashboardCardOut(
            id=card.id,
            site_id=card.site.id,
            variable_id=card.variable_id,
            variable_name=card.variable_name,
            card_type=card.card_type,
            config=card.config,
            position=card.position,
            layout=card.layout,
            created_at=card.created_at,
            updated_at=card.updated_at,
        ))
    
    return result


@router.post(
    "/{site_id}/dashboard/cards",
    response=list[DashboardCardOut],
    auth=AuthBearer(
        [
            ("scada:site:edit", "x"),
            ("scada:site:permit:{site_id}", "w"),
        ]
    ),
)
@api_schema
def save_dashboard_cards(request, site_id: int, payload: list[DashboardCardIn]):
    """保存站点的 Dashboard 卡片列表（批量保存/更新）"""
    site = get_object_or_404(Site, id=site_id)
    
    # 删除所有现有卡片
    DashboardCard.objects.filter(site=site).delete()
    
    # 创建新卡片
    cards = []
    for idx, card_data in enumerate(payload):
        config_dict = {}
        if card_data.config:
            if card_data.config.time_interval:
                config_dict["timeInterval"] = card_data.config.time_interval
            if card_data.config.aggregation:
                config_dict["aggregation"] = card_data.config.aggregation
            if card_data.config.precision is not None:
                config_dict["precision"] = card_data.config.precision
            if card_data.config.unit:
                config_dict["unit"] = card_data.config.unit
        
        layout_dict = None
        if card_data.layout:
            layout_dict = {}
            if card_data.layout.x is not None:
                layout_dict["x"] = card_data.layout.x
            if card_data.layout.y is not None:
                layout_dict["y"] = card_data.layout.y
        
        card = DashboardCard.objects.create(
            site=site,
            variable_id=card_data.variable_id,
            variable_name=card_data.variable_name,
            card_type=card_data.card_type,
            config=config_dict,
            position=card_data.position if card_data.position is not None else idx,
            layout=layout_dict,
        )
        cards.append(card)
    
    # 返回保存的卡片
    result = []
    for card in cards:
        result.append(DashboardCardOut(
            id=card.id,
            site_id=card.site.id,
            variable_id=card.variable_id,
            variable_name=card.variable_name,
            card_type=card.card_type,
            config=card.config,
            position=card.position,
            layout=card.layout,
            created_at=card.created_at,
            updated_at=card.updated_at,
        ))
    
    return result
