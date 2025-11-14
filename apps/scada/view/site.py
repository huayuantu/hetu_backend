from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from ninja import Router
from ninja.errors import HttpError

from apps.scada.models import DashboardCard, Site, SiteStatistic
from apps.scada.schema.site import (
    DashboardCardIn,
    DashboardCardOut,
    GlobalStatisticsOut,
    SiteIn,
    SiteOptionOut,
    SiteOut,
    SitePermit,
    SitePermitType,
    SiteStatisticIn,
    SiteStatisticOut,
    SiteStatisticValueOut,
    SiteVariableCountOut,
)
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
    """选项列表，返回用户有权限的站点及其权限信息"""
    import logging

    logger = logging.getLogger(__name__)

    enforcer = get_enforcer()
    username = request.auth["username"]

    logger.info(f"[站点权限] 用户 {username} 请求站点列表")

    # 获取当前用户对所有站点的权限
    policies = [
        policy
        for policy in enforcer.get_filtered_policy(0, username)
        if policy[1].startswith("scada:site:permit:")
    ]

    logger.info(f"[站点权限] 用户 {username} 的 Casbin 策略数量: {len(policies)}")
    for policy in policies:
        logger.info(f"[站点权限] 策略: {policy}")

    # 构建站点权限映射：site_id -> permission (r 或 w)
    site_permissions: dict[int, str] = {}
    for _, target, permission in policies:
        site_id = int(target.split(":")[-1])
        # w 权限优先于 r 权限
        if permission == "w":
            site_permissions[site_id] = "w"
            logger.info(f"[站点权限] 站点 {site_id}: 读写权限 (w)")
        elif permission == "r" and site_id not in site_permissions:
            site_permissions[site_id] = "r"
            logger.info(f"[站点权限] 站点 {site_id}: 只读权限 (r)")

    # 获取所有站点
    sites = Site.objects.all()

    # 构建返回结果，包含权限信息
    result = []
    for site in sites:
        permit = site_permissions.get(site.id, None)
        logger.info(f"[站点权限] 站点 {site.id} ({site.name}): 权限={permit}")
        result.append(
            SiteOptionOut(
                id=site.id,
                name=site.name,
                status=site.status,
                longitude=site.longitude,
                latitude=site.latitude,
                permit=permit,
            )
        )

    logger.info(f"[站点权限] 用户 {username} 返回 {len(result)} 个站点")
    return result


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
    from django.core.cache import cache

    # Verify site exists
    get_object_or_404(Site, id=site_id)
    statistic = SiteStatistic(
        site_id=site_id, **payload.dict(exclude={"variable_ids": True})
    )
    statistic.save()

    statistic.variables.set(payload.variable_ids)

    # 清除该站点的统计值缓存
    cache.delete(f"statistic:{site_id}:{statistic.name}")
    cache.delete(f"statistic:{site_id}:{statistic.id}")

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
    """计算统计值并返回（已优化：并行查询 + 缓存）"""
    import concurrent.futures
    from collections import defaultdict

    from django.core.cache import cache

    from apps.scada.utils.promql import PrometheusQueryError, promql_query

    # 构建缓存键
    cache_key = f"statistic:{site_id}:{statistic_id or statistic_name}"

    # 尝试从缓存获取
    cached_result = cache.get(cache_key)
    if cached_result:
        return cached_result

    if statistic_id:
        statistic = get_object_or_404(SiteStatistic, id=statistic_id, site_id=site_id)
    elif statistic_name:
        statistic = SiteStatistic.objects.filter(
            site_id=site_id, name=statistic_name
        ).first()
        if not statistic:
            # 通过名字找不到统计量就直接返回0
            result = SiteStatisticValueOut(id=-1, name=statistic_name)
            # 缓存空结果5秒，避免频繁查询
            cache.set(cache_key, result, timeout=5)
            return result
    else:
        raise HttpError(400, "指定statistic_id或指定statistic_name")

    output = SiteStatisticValueOut.from_orm(statistic)

    # 优化：使用 prefetch_related 预加载 ManyToMany 关系和相关对象
    variables = statistic.variables.prefetch_related("module").all()

    # 按模块分组变量
    module_vars = defaultdict(list)
    for v in variables:
        output.variable_ids.append(v.id)
        module_vars[v.module.module_number].append(v)

    values = []
    timestamp = 0

    # 优化：并行查询 Prometheus（多个模块同时查询）
    def query_module(module_number: str, vars_list: list):
        """查询单个模块的变量值"""
        var_names = [v.name for v in vars_list]
        query_str = f'grm_{module_number}_gauge{{name=~"{"|".join(var_names)}"}}'

        try:
            query_data = promql_query(query_str)
            result_dict = {}
            for result in query_data.get("data", {}).get("result", []):
                metric_name = result.get("metric", {}).get("name")
                if metric_name:
                    result_dict[metric_name] = result.get("value", [0, 0])

            # 返回该模块的变量值列表
            module_values = []
            module_timestamp = 0
            for v in vars_list:
                if v.name in result_dict:
                    value_data = result_dict[v.name]
                    module_timestamp = max(module_timestamp, int(value_data[0]))
                    module_values.append(float(value_data[1]))

            return module_values, module_timestamp
        except (PrometheusQueryError, Exception):
            # 记录错误但不中断其他模块的查询
            return [], 0

    # 使用线程池并行查询所有模块
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(query_module, module_number, vars_list): module_number
            for module_number, vars_list in module_vars.items()
        }

        for future in concurrent.futures.as_completed(futures):
            try:
                module_values, module_timestamp = future.result()
                values.extend(module_values)
                timestamp = max(timestamp, module_timestamp)
            except Exception:
                # 某个模块查询失败，继续处理其他模块
                continue

    # 目前只支持累加
    output.value = sum(values)
    output.timestamp = timestamp

    # 缓存结果30秒
    cache.set(cache_key, output, timeout=30)
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
    from django.core.cache import cache

    statistic = get_object_or_404(SiteStatistic, id=statistic_id, site_id=site_id)
    old_name = statistic.name  # 保存旧名称用于清除缓存
    statistic.name = payload.name
    statistic.method = payload.method
    statistic.save()

    statistic.variables.set(payload.variable_ids)

    # 清除该站点的统计值缓存（包括旧名称和新名称）
    cache.delete(f"statistic:{site_id}:{old_name}")
    cache.delete(f"statistic:{site_id}:{statistic.name}")
    cache.delete(f"statistic:{site_id}:{statistic_id}")

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
    from django.core.cache import cache

    statistic = get_object_or_404(SiteStatistic, id=statistic_id, site_id=site_id)
    statistic_name = statistic.name  # 保存名称用于清除缓存
    statistic.delete()

    # 清除该站点的统计值缓存
    cache.delete(f"statistic:{site_id}:{statistic_name}")
    cache.delete(f"statistic:{site_id}:{statistic_id}")

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
    from collections import defaultdict

    from apps.scada.models import Variable

    # 解析站点ID列表
    if site_ids:
        site_id_list = [int(sid.strip()) for sid in site_ids.split(",") if sid.strip()]
        if not site_id_list:
            return []
    else:
        # 如果没有提供站点ID，返回所有站点
        site_id_list = None

    # 使用一次查询获取所有站点的变量总数
    if site_id_list:
        variable_counts = (
            Variable.objects.filter(module__site_id__in=site_id_list)
            .values("module__site_id")
            .annotate(variable_count=Count("id"))
        )
    else:
        variable_counts = Variable.objects.values("module__site_id").annotate(
            variable_count=Count("id")
        )

    # 按站点ID汇总
    site_counts = defaultdict(int)
    for item in variable_counts:
        site_id = item["module__site_id"]
        count = item["variable_count"]
        site_counts[site_id] += count

    # 构建返回结果
    result = []
    for site_id, count in site_counts.items():
        result.append(SiteVariableCountOut(site_id=site_id, variable_count=count))

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
        result.append(
            DashboardCardOut(
                id=card.id,
                site_id=card.site.id,
                variable_id=card.variable_id,
                variable_name=card.variable_name,
                title=card.title
                if card.title
                else card.variable_name,  # 如果没有标题，使用变量名称
                card_type=card.card_type,
                config=card.config,
                position=card.position,
                layout=card.layout,
                created_at=card.created_at,
                updated_at=card.updated_at,
            )
        )

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
            title=card_data.title
            if card_data.title
            else card_data.variable_name,  # 如果没有标题，使用变量名称
            card_type=card_data.card_type,
            config=config_dict,
            position=card_data.position if card_data.position is not None else idx,
            layout=layout_dict,
        )
        cards.append(card)

    # 返回保存的卡片
    result = []
    for card in cards:
        result.append(
            DashboardCardOut(
                id=card.id,
                site_id=card.site.id,
                variable_id=card.variable_id,
                variable_name=card.variable_name,
                title=card.title
                if card.title
                else card.variable_name,  # 如果没有标题，使用变量名称
                card_type=card.card_type,
                config=card.config,
                position=card.position,
                layout=card.layout,
                created_at=card.created_at,
                updated_at=card.updated_at,
            )
        )

    return result


@router.get(
    "/statistics/global",
    response=GlobalStatisticsOut,
    auth=AuthBearer(
        [
            ("scada:site:info", "x"),
        ]
    ),
)
@api_schema
def get_global_statistics(request):
    """获取全局统计数据（聚合接口，一次性返回所有统计数据）
    
    优化：使用一次查询获取所有统计数据，避免前端多次请求
    """
    import concurrent.futures
    from collections import defaultdict
    
    from django.core.cache import cache
    from django.db.models import Count, Max, Q
    
    from apps.scada.models import Variable, Notify
    
    # 使用缓存，避免频繁查询（缓存30秒）
    cache_key = "global_statistics"
    cached_result = cache.get(cache_key)
    if cached_result:
        return cached_result
    
    # 1. 接入站点数：过滤掉 status=0 (connecting) 的站点
    total_site = Site.objects.exclude(status=0).count()
    
    # 2. 监控点数：使用一次查询获取所有站点的变量总数
    total_variables = Variable.objects.count()
    
    # 3. 处理总量：获取所有站点的"处理总量"统计值之和
    # 兼容之前的站点接口：优先使用统计配置，如果没有配置则跳过（不累加0值）
    # 获取所有非 connecting 状态的站点
    sites = Site.objects.exclude(status=0)
    total_water = 0.0
    
    def get_site_water_statistic(site_id: int):
        """获取单个站点的处理总量统计值
        
        兼容逻辑：
        1. 优先使用 SiteStatistic 配置的"处理总量"统计
        2. 如果没有配置，返回 None（而不是0），避免累加无效值
        3. 如果查询失败，返回 None
        """
        try:
            statistic = SiteStatistic.objects.filter(
                site_id=site_id, name="处理总量"
            ).first()
            if not statistic:
                # 没有统计配置，返回 None 表示跳过
                return None
            
            # 使用已有的 get_statistic_value 逻辑，但需要优化
            # 这里直接调用内部逻辑，避免重复的缓存检查
            from apps.scada.utils.promql import PrometheusQueryError, promql_query
            
            variables = statistic.variables.prefetch_related("module").all()
            if not variables.exists():
                # 统计配置存在但没有关联变量，返回 None
                return None
            
            module_vars = defaultdict(list)
            for v in variables:
                module_vars[v.module.module_number].append(v)
            
            values = []
            
            def query_module(module_number: str, vars_list: list):
                """查询单个模块的变量值"""
                var_names = [v.name for v in vars_list]
                query_str = f'grm_{module_number}_gauge{{name=~"{"|".join(var_names)}"}}'
                
                try:
                    query_data = promql_query(query_str)
                    result_dict = {}
                    for result in query_data.get("data", {}).get("result", []):
                        metric_name = result.get("metric", {}).get("name")
                        if metric_name:
                            result_dict[metric_name] = result.get("value", [0, 0])
                    
                    module_values = []
                    for v in vars_list:
                        if v.name in result_dict:
                            value_data = result_dict[v.name]
                            module_values.append(float(value_data[1]))
                    
                    return module_values
                except (PrometheusQueryError, Exception):
                    return []
            
            # 并行查询所有模块
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = {
                    executor.submit(query_module, module_number, vars_list): module_number
                    for module_number, vars_list in module_vars.items()
                }
                
                for future in concurrent.futures.as_completed(futures):
                    try:
                        module_values = future.result()
                        values.extend(module_values)
                    except Exception:
                        continue
            
            # 如果没有任何值，返回 None
            if not values:
                return None
            
            return sum(values)
        except Exception as e:
            # 记录错误但不中断其他站点的查询
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"获取站点 {site_id} 的处理总量统计失败: {e}")
            return None
    
    # 并行获取所有站点的处理总量
    site_ids = list(sites.values_list('id', flat=True))
    if site_ids:
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(get_site_water_statistic, site_id): site_id
                for site_id in site_ids
            }
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    # 只累加有效值（非 None）
                    if result is not None:
                        total_water += result
                except Exception:
                    continue
    
    # 4. 处理预警：获取通知计数（激活的告警数 + 总告警数）
    # 直接使用 get_notify_count 的内部逻辑，避免装饰器包装问题
    from django.db.models import Count, Max, Q
    from apps.scada.models import Notify
    
    notifies = Notify.objects.all()
    
    # 使用 annotate 一次性计算所有统计值
    stats = notifies.aggregate(
        total=Count("id"), acknowledged=Count("id", filter=Q(ack=True))
    )
    
    # 激活的数量：每个 external_id 的最新记录，且 title 以"触发警告"结尾，且 ack=False
    latest_notify_ids = (
        notifies.values("external_id")
        .annotate(latest_id=Max("id"), latest_notified_at=Max("notified_at"))
        .values("latest_id")
    )
    
    activated = notifies.filter(
        id__in=latest_notify_ids, title__endswith="触发警告", ack=False
    ).count()
    
    total_warning = (activated or 0) + (stats["total"] or 0)
    
    result = GlobalStatisticsOut(
        total_site=total_site,
        total_variables=total_variables,
        total_water=total_water,
        total_warning=total_warning
    )
    
    # 缓存结果30秒
    cache.set(cache_key, result, timeout=30)
    return result
