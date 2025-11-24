import logging
import threading
import time
from datetime import datetime, timedelta

import requests
from django.conf import settings
from django.db.models import F, Q
from django.shortcuts import get_object_or_404
from ninja import Router
from ninja.errors import HttpError
from prometheus_client import (
    CollectorRegistry,
    Gauge,
    delete_from_gateway,
    push_to_gateway,
)

from apps.scada.models import Module, Variable
from apps.scada.schema.variable import (
    QueryRangeIn,
    ReadValueIn,
    ReadValueOut,
    VariableIn,
    VariableOptionOut,
    VariableOut,
    VariableUpdateIn,
    WriteValueIn,
    WriteValueOut,
)
from apps.scada.utils.grm.schemas import GrmVariable
from apps.scada.utils.pool import get_grm_client
from apps.scada.utils.promql import (
    PrometheusQueryError,
    promql_query,
    promql_query_range,
)
from apps.sys.utils import (
    AuthBearer,
    AuthBearerTokenOrPerm,
)
from utils.schema.base import api_schema
from utils.schema.paginate import api_paginate

router = Router()
logger = logging.getLogger(__name__)


@router.get(
    "/{site_id}/variable/{variable_id}/range",
    response=ReadValueOut,
    auth=AuthBearer(
        [
            ("scada:variable:read", "x"),
            ("scada:site:permit:{site_id}", "r"),
        ]
    ),
)
@api_schema
def read_range(
    request,
    site_id: int,
    variable_id: int,
    offset: int = None,
    duration: str = "1h",
    step: int = 15,
):
    var = get_object_or_404(Variable, id=variable_id, module__site_id=site_id)
    query_str = "grm_" + var.module.module_number + "_gauge"
    query_str += '{name="' + var.name + '"}'

    # 处理 duration 参数
    units = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days", "w": "weeks"}
    duration_seconds = int(
        timedelta(**{units[duration[-1]]: int(duration[:-1])}).total_seconds()
    )

    # 处理 offset 参数
    if offset is None:
        offset = int(datetime.now().timestamp())

    try:
        result = promql_query_range(query_str, offset - duration_seconds, offset, step)
    except PrometheusQueryError as e:
        raise HttpError(500, f"Prometheus Query Error: {e}") from e
    except requests.RequestException as e:
        raise HttpError(500, f"Request Error: {e}") from e

    # 格式参考 https://prometheus.io/docs/prometheus/latest/querying/api/#range-vectors
    values: list[ReadValueOut.Value] = []
    out = ReadValueOut.from_orm(var)
    for ret in result:
        for v in ret["values"]:
            values.append(ReadValueOut.Value(timestamp=v[0], value=float(v[1])))
        break
    out.values = values
    return out


@router.post(
    "/{site_id}/variable/values",
    response=list[ReadValueOut],
    auth=AuthBearer(
        [
            ("scada:variable:read", "x"),
            ("scada:site:permit:{site_id}", "r"),
        ]
    ),
)
@api_schema
def read_values(
    request,
    site_id: int,
    payload: ReadValueIn,
):
    """批量读取变量值（优化：在内存中分组，避免 N+1 查询）"""
    # 一次性查询所有变量，使用 select_related 预加载 module
    vars = Variable.objects.filter(
        id__in=payload.variable_ids,
        module__site_id=site_id
    ).select_related("module")

    # 优化：在内存中按模块分组，避免循环中的数据库查询
    from collections import defaultdict
    module_vars_map = defaultdict(lambda: {"module_number": None, "vars": []})

    for v in vars:
        module_id = v.module_id
        if module_vars_map[module_id]["module_number"] is None:
            module_vars_map[module_id]["module_number"] = v.module.module_number
        module_vars_map[module_id]["vars"].append(v)

    outlist: list[ReadValueOut] = []

    # 数据是按模块存储，所以变量按模块获取
    for module_data in module_vars_map.values():
        module_number = module_data["module_number"]
        module_vars = module_data["vars"]

        if module_number is None or not module_vars:
            continue

        assert isinstance(module_number, str), "module_number must be a string"
        query_str = "grm_" + module_number + "_gauge"
        query_str += '{name=~"' + "|".join([v.name for v in module_vars]) + '"}'

        try:
            query_data = promql_query(query_str)
        except PrometheusQueryError as e:
            raise HttpError(500, f"Prometheus Query Error: {e}") from e
        except requests.RequestException as e:
            raise HttpError(500, f"Request Error: {e}") from e

        # 构建输出结构：只处理属于当前模块的变量
        result_list = query_data.get("data", {}).get("result", []) if query_data else []
        for v in module_vars:
            out = ReadValueOut.from_orm(v)
            for result in result_list:
                if result["metric"]["name"] == v.name:
                    value = ReadValueOut.Value(
                        timestamp=result["value"][0], value=float(result["value"][1])
                    )
                    out.values.append(value)
                    break
            outlist.append(out)

    return outlist


@router.post(
    "/{site_id}/variable/range",
    response=list[ReadValueOut],
    auth=AuthBearer(
        [
            ("scada:variable:read", "x"),
            ("scada:site:permit:{site_id}", "r"),
        ]
    ),
)
@api_schema
def query_range(
    request,
    site_id: int,
    payload: QueryRangeIn,
):
    """批量查询变量历史数据，支持聚合函数（优化：在内存中分组，避免 N+1 查询）"""
    # 验证时间范围
    if payload.start_time >= payload.end_time:
        raise HttpError(400, "start_time must be less than end_time")

    # 验证变量是否存在且属于指定站点
    # 优化：直接查询并转换为列表，避免 count() 查询
    vars = Variable.objects.filter(
        id__in=payload.variable_ids,
        module__site_id=site_id
    ).select_related("module")

    vars_list = list(vars)
    if len(vars_list) != len(payload.variable_ids):
        raise HttpError(404, "Some variables not found or not belong to this site")

    # 优化：在内存中按模块分组，避免循环中的数据库查询
    from collections import defaultdict
    module_vars_map = defaultdict(lambda: {"module_number": None, "vars": []})

    for v in vars_list:
        module_id = v.module_id
        if module_vars_map[module_id]["module_number"] is None:
            module_vars_map[module_id]["module_number"] = v.module.module_number
        module_vars_map[module_id]["vars"].append(v)

    outlist: list[ReadValueOut] = []

    # 数据是按模块存储，所以变量按模块获取
    for module_data in module_vars_map.values():
        module_number = module_data["module_number"]
        module_vars = module_data["vars"]

        if module_number is None or not module_vars:
            continue

        assert isinstance(module_number, str), "module_number must be a string"
        # 构建基础 PromQL 查询
        base_query = "grm_" + module_number + "_gauge"
        base_query += '{name=~"' + "|".join([v.name for v in module_vars]) + '"}'

        # 如果指定了聚合方式，应用聚合函数
        if payload.aggregation:
            aggregation_map = {
                "avg": "avg_over_time",
                "min": "min_over_time",
                "max": "max_over_time",
            }
            if payload.aggregation not in aggregation_map:
                raise HttpError(
                    400,
                    f"Invalid aggregation: {payload.aggregation}. Must be 'avg', 'min', or 'max'",
                )
            # 使用聚合函数，格式：{aggregation}_over_time(metric[{step}s])
            query_str = (
                f"{aggregation_map[payload.aggregation]}({base_query}[{payload.step}s])"
            )
        else:
            # 不使用聚合，直接查询原始数据
            query_str = base_query

        try:
            result = promql_query_range(
                query_str, payload.start_time, payload.end_time, payload.step
            )
        except PrometheusQueryError as e:
            raise HttpError(500, f"Prometheus Query Error: {e}") from e
        except requests.RequestException as e:
            raise HttpError(500, f"Request Error: {e}") from e

        # 构建输出结构
        result_list = result if result else []
        for v in module_vars:
            out = ReadValueOut.from_orm(v)
            # 从 Prometheus 结果中查找匹配的变量
            for ret in result_list:
                metric_name = ret.get("metric", {}).get("name")
                if metric_name == v.name:
                    # 处理 values 数组
                    for value_tuple in ret.get("values", []):
                        timestamp = int(value_tuple[0])
                        value = float(value_tuple[1])
                        out.values.append(
                            ReadValueOut.Value(timestamp=timestamp, value=value)
                        )
                    break
            outlist.append(out)

    return outlist


@router.post(
    "/{site_id}/module/{module_id}/variable",
    response=VariableOut,
    auth=AuthBearer(
        [
            ("scada:variable:add", "x"),
            ("scada:site:permit:{site_id}", "w"),
        ]
    ),
)
@api_schema
def create_variable(
    request,
    site_id: int,
    module_id: int,
    payload: VariableIn,
):
    """创建变量"""

    module = get_object_or_404(Module, id=module_id, site_id=site_id)
    v = Variable(module_id=module.id, **payload.dict())
    v.save()
    v.site_id = site_id
    return v


@router.get(
    "/{site_id}/module/{module_id}/variable/options",
    response=list[VariableOptionOut],
    auth=AuthBearer(
        [
            ("scada:variable:edit", "x"),
            ("scada:site:permit:{site_id}", "r"),
        ]
    ),
)
@api_schema
def get_variable_option_list(
    request,
    site_id: int,
    module_id: int,
    group: str = None,
):
    """获取模块的变量选项"""

    vs = Variable.objects.filter(module_id=module_id, module__site_id=site_id)

    if group:
        vs = vs.filter(group=group)

    return vs.all()


@router.get(
    "/{site_id}/module/{module_id}/variable/groups",
    response=list[str],
    auth=AuthBearer(
        [
            ("scada:variable:edit", "x"),
            ("scada:site:permit:{site_id}", "r"),
        ]
    ),
)
@api_schema
def get_variable_group_list(
    request,
    site_id: int,
    module_id: int,
    keywords: str = None,
):
    """获取变量组"""

    gs = Variable.objects.filter(module_id=module_id, module__site_id=site_id)

    if keywords:
        gs = gs.filter(Q(group__icontains=keywords))

    return gs.values("group").distinct().values_list("group", flat=True)


@router.put(
    "/{site_id}/module/{module_id}/variable/{variable_id}",
    response=VariableOut,
    auth=AuthBearer(
        [
            ("scada:variable:edit", "x"),
            ("scada:site:permit:{site_id}", "w"),
        ]
    ),
)
@api_schema
def update_variable(
    request,
    site_id: int,
    module_id: int,
    variable_id: int,
    payload: VariableUpdateIn,
):
    """更新变量信息"""

    v = get_object_or_404(
        Variable, id=variable_id, module_id=module_id, module__site_id=site_id
    )
    v.type = payload.type
    v.rw = payload.rw
    v.pulse = payload.pulse
    v.details = payload.details
    v.save()
    v.site_id = site_id
    return v


def write_local_var(variable: Variable, payload: WriteValueIn):
    """通过pushgateway实现模块手动设置的本地的变量"""

    # 创建一个 CollectorRegistry 对象
    registry = CollectorRegistry()

    # 创建一个 Gauge 指标
    gauge = Gauge(
        f"grm_{variable.module.module_number}_gauge",
        str(variable.details),
        registry=registry,
    )

    # 设置指标的值
    gauge.set(payload.value)

    # 设置标签
    labels = {"name": variable.name, "type": variable.type, "local": "true"}

    # 写入
    push_to_gateway(
        settings.PUSHGATEWAY_URL,
        job="grm_local",
        registry=registry,
        grouping_key=labels,
    )


@router.put(
    "/{site_id}/variable/values",
    response=list[WriteValueOut],
    auth=AuthBearerTokenOrPerm(
        [
            ("scada:variable:write", "x"),
            ("scada:site:permit:{site_id}", "w"),
        ]
    ),  # OR逻辑：API token认证（服务账号）或用户有写入权限
)
@api_schema
def update_variable_values(
    request,
    site_id: int,
    payload: list[WriteValueIn],
):
    """写模块变量接口"""

    outlist: list[WriteValueOut] = []

    # 逐个写入
    for p in payload:
        out = WriteValueOut(id=p.id)
        var = Variable.objects.filter(
            id=p.id,
            module__site_id=site_id,
        ).first()

        if not var:
            out.error = 404
        elif not var.rw:
            out.error = 422
        elif not var.local:
            # 获取客户端
            client = get_grm_client(var.module)

            grm_write_list = [
                GrmVariable(
                    module_number=var.module.module_number,
                    type=var.type,
                    name=var.name,
                    value=p.value,
                    group=var.group,
                )
            ]
            try:
                # 写远程GRM设备
                client.write(grm_write_list)
                out.error = grm_write_list[0].write_error
            except Exception:
                out.error = 503
        else:
            # 本地pushgateway变量
            try:
                write_local_var(var, p)
            except Exception:
                out.error = 503

        # 若为脉冲变量且本次写入成功（仅远程变量），则2秒后回落为0
        if out.error == 0 and var and var.pulse and not var.local:

            def _reset_to_zero(
                _module=var.module,
                _type=var.type,
                _name=var.name,
                _group=var.group,
            ):
                try:
                    time.sleep(2)
                    # 直接写入远程GRM为0（不再查询数据库，也不处理本地变量）
                    client0 = get_grm_client(_module)
                    grm_write_list0 = [
                        GrmVariable(
                            module_number=_module.module_number,
                            type=_type,
                            name=_name,
                            value=0.0,
                            group=_group,
                        )
                    ]
                    client0.write(grm_write_list0)
                except Exception:
                    logger.exception(
                        "Pulse zero-reset task failed: module=%s name=%s",
                        _module.module_number,
                        _name,
                    )

            t = threading.Thread(target=_reset_to_zero, daemon=True)
            t.start()

        outlist.append(out)

    return outlist


@router.get(
    "/{site_id}/module/{module_id}/variable/{variable_id}",
    response=VariableOut,
    auth=AuthBearer(
        [
            ("scada:variable:edit", "x"),
            ("scada:site:permit:{site_id}", "r"),
        ]
    ),
)
@api_schema
def get_variable_info(
    request,
    site_id: int,
    module_id: int,
    variable_id: int,
):
    """获取变量信息"""

    var = get_object_or_404(
        Variable, id=variable_id, module_id=module_id, module__site_id=site_id
    )
    var.site_id = site_id
    return VariableOut.from_orm(var)


@router.get(
    "/{site_id}/module/{module_id}/variable",
    response=list[VariableOut],
    auth=AuthBearer(
        [
            ("scada:variable:edit", "x"),
            ("scada:site:permit:{site_id}", "r"),
        ]
    ),
)
@api_paginate
def get_variable_list(
    request, site_id: int, module_id: int, keywords: str = None, group: str = None
):
    """列出模块的所有变量"""
    fields = [field.name for field in Variable._meta.get_fields()]
    fields.append("module__site_id")
    vars = Variable.objects.filter(
        module_id=module_id,
        module__site_id=site_id,
    ).annotate(site_id=F("module__site_id"))

    if group:
        vars = vars.filter(group=group)

    if keywords:
        vars = vars.filter(Q(name__icontains=keywords))

    return vars.all()


@router.delete(
    "/{site_id}/module/{module_id}/variable/{variable_id}",
    response=str,
    auth=AuthBearer(
        [
            ("scada:variable:delete", "x"),
            ("scada:site:permit:{site_id}", "w"),
        ]
    ),
)
@api_schema
def delete_variable(request, site_id: int, module_id: int, variable_id: int):
    """删除变量接口"""

    var = get_object_or_404(
        Variable, id=variable_id, module_id=module_id, module__site_id=site_id
    )

    # 本地变量要从pushgateway删除
    if var.local:
        labels = {"name": var.name, "type": var.type, "local": "true"}

        delete_from_gateway(
            settings.PUSHGATEWAY_URL,
            job="grm_local",
            grouping_key=labels,
        )

    var.delete()
    return "OK"
