"""规则可视化 DSL：解析 / 校验 / 求值。

语法（单条规则）：
    WHEN <metric> <op> <threshold> [FOR <scope>] THEN [SUGGEST] <dimension> "<模板>" [WITH SEVERITY <high|mid|low>]

示例：
    WHEN acos > 40 FOR campaign THEN SUGGEST bid "活动「{scope}」ACOS 达 {value}%，建议下调竞价" WITH SEVERITY mid
    WHEN ctr < 0.2 FOR keyword THEN listing "关键词「{scope}」CTR 仅 {value}%" WITH SEVERITY low

说明：
- <metric> 取自统一指标口径（impressions/clicks/ctr/cpc/spend/orders/cvr/sales/acos/roas/tacos）。
- <threshold> 与指标同单位：百分比指标（ctr/cvr/acos/tacos）按百分比数值填写（如 0.2 表示 0.2%）。
- <scope> 决定聚合粒度：account（默认，整体汇总）/ campaign / keyword / adgroup / ad_format / placement / targeting。
- <dimension> 取自 12 维分析维度之一。
- 模板支持占位符：{metric} {metric_code} {op} {op_sym} {threshold} {value} {scope} {dimension} {entities} {name}。
"""
import re

from .metrics import METRICS, aggregate
from .rules import DIMENSIONS

METRIC_CODES = [m["code"] for m in METRICS]
METRIC_NAME = {m["code"]: m["name_zh"] for m in METRICS}
# 百分比类指标按百分比数值比较（ctr/cvr/acos/tacos 已是百分比数值）；cpc/spend 为金额
PCT_METRICS = {"ctr", "cvr", "acos", "tacos"}
MONEY_METRICS = {"cpc", "spend"}

OPS = {
    ">": "gt", ">=": "gte", "<": "lt", "<=": "lte", "==": "eq", "!=": "ne",
}
OP_SYMBOL = {">": ">", ">=": "≥", "<": "<", "<=": "≤", "==": "=", "!=": "≠"}

SCOPES = ["account", "campaign", "keyword", "adgroup", "ad_format", "placement", "targeting"]
SCOPE_GROUP = {
    "account": "campaign",        # account 用 campaign 聚合后取 summary
    "campaign": "campaign",
    "keyword": "keyword",
    "adgroup": "adgroup",
    "ad_format": "ad_format",
    "placement": "placement",
    "targeting": "targeting",
}
SCOPE_NAME = {
    "account": "账户整体", "campaign": "广告活动", "keyword": "关键词",
    "adgroup": "广告组", "ad_format": "广告格式", "placement": "投放位置", "targeting": "定向",
}

DIMENSION_CODES = [d["code"] for d in DIMENSIONS]
DIMENSION_NAME = {d["code"]: d["name_zh"] for d in DIMENSIONS}

SEVERITY_PRIORITY = {"high": "P0", "mid": "P1", "low": "P2"}
SEVERITIES = ["high", "mid", "low"]


_DSPL_RE = re.compile(
    r"""
    \bWHEN\s+
    (?P<metric>\w+)\s*
    (?P<op>>=|<=|==|!=|>|<)\s*
    (?P<threshold>[+-]?[\d.]+)\s*
    (?:FOR\s+(?P<scope>\w+)\s+)?
    THEN\s+(?:SUGGEST\s+)?
    (?P<dimension>\w+)\s+
    "(?P<template>.*?)"\s*
    (?:WITH\s+SEVERITY\s+(?P<severity>\w+))?
    """,
    re.IGNORECASE | re.VERBOSE,
)


def unit_of(metric):
    if metric in PCT_METRICS:
        return "%"
    if metric in MONEY_METRICS:
        return "$"
    return ""


def fmt_value(metric, v):
    u = unit_of(metric)
    if u == "%":
        return f"{v:.3f}%"
    if u == "$":
        return f"${v:.2f}"
    return f"{v:.2f}" if isinstance(v, float) else str(v)


def parse_dsl(text):
    """解析 DSL 文本为结构化 dict；语法错误时 valid=False 并给出 error。"""
    if text is None:
        text = ""
    text = text.strip()
    m = _DSPL_RE.search(text)
    if not m:
        return {"valid": False, "error": "无法解析：语法应为 "
                "WHEN <指标> <运算符> <阈值> [FOR <作用域>] THEN [SUGGEST] <维度> \"<模板>\" [WITH SEVERITY <级别>]",
                "raw": text}
    scope = (m.group("scope") or "account").lower()
    severity = (m.group("severity") or "mid").lower()
    try:
        threshold = float(m.group("threshold"))
    except ValueError:
        return {"valid": False, "error": "阈值必须为数字", "raw": text}
    return {
        "valid": True,
        "error": None,
        "metric": m.group("metric").lower(),
        "op": m.group("op"),
        "op_sym": OP_SYMBOL.get(m.group("op"), m.group("op")),
        "threshold": threshold,
        "scope": scope,
        "dimension": m.group("dimension").lower(),
        "template": m.group("template"),
        "severity": severity,
        "raw": text,
    }


def validate_rule(d):
    """语义校验：返回错误列表（空列表表示通过）。d 为 parse_dsl 的结果。"""
    errs = []
    if not d.get("valid"):
        errs.append(d.get("error") or "语法错误")
        return errs
    if d["metric"] not in METRIC_CODES:
        errs.append(f"未知指标「{d['metric']}」，可选：{', '.join(METRIC_CODES)}")
    if d["op"] not in OPS:
        errs.append(f"不支持的运算符「{d['op']}」")
    if d["scope"] not in SCOPES:
        errs.append(f"未知作用域「{d['scope']}」，可选：{', '.join(SCOPES)}")
    if d["dimension"] not in DIMENSION_CODES:
        errs.append(f"未知维度「{d['dimension']}」，可选：{', '.join(DIMENSION_CODES)}")
    if d["severity"] not in SEVERITIES:
        errs.append(f"未知严重度「{d['severity']}」，可选：{', '.join(SEVERITIES)}")
    if not d["template"] or not d["template"].strip():
        errs.append("建议模板不能为空")
    return errs


def check_dsl(text):
    """便捷入口：解析 + 校验，返回 {ok, errors, parsed}。"""
    parsed = parse_dsl(text)
    errs = validate_rule(parsed)
    return {"ok": len(errs) == 0, "errors": errs, "parsed": parsed}


def _cmp(a, op, b):
    if op == ">":
        return a > b
    if op == ">=":
        return a >= b
    if op == "<":
        return a < b
    if op == "<=":
        return a <= b
    if op == "==":
        return a == b
    if op == "!=":
        return a != b
    return False


def _safe_format(tpl, ctx):
    """模板格式化：缺失键回退为占位符，避免异常。"""
    def repl(mo):
        key = mo.group(1)
        return str(ctx.get(key, "{" + key + "}"))
    return re.sub(r"\{(\w+)\}", repl, tpl or "")


def evaluate_rule(db, shop_id, d1, d2, d, target_acos=35.0):
    """按 DSL 规则求值，命中则返回 0 或 1 条 ActionItem（dict）。"""
    if not d.get("valid"):
        return []
    metric = d["metric"]
    op = d["op"]
    threshold = d["threshold"]
    scope = d["scope"]
    group_by = SCOPE_GROUP[scope]

    if scope == "account":
        agg = aggregate(db, shop_id, d1, d2, group_by="campaign")
        entities = [{"label": SCOPE_NAME["account"], "value": agg["summary"].get(metric, 0), "row": agg["summary"]}]
    else:
        agg = aggregate(db, shop_id, d1, d2, group_by=group_by, limit=100000)
        entities = []
        for r in agg["rows"]:
            # 取用于展示的实体名
            if scope == "campaign":
                label = r.get("campaign_name") or r.get("campaign_id") or "?"
            elif scope == "keyword":
                label = r.get("keyword_text") or "?"
            elif scope == "adgroup":
                label = r.get("adgroup_name") or r.get("adgroup_id") or "?"
            elif scope == "ad_format":
                label = r.get("ad_format") or "?"
            elif scope == "placement":
                label = r.get("placement") or "(未填)"
            elif scope == "targeting":
                label = r.get("targeting") or "?"
            else:
                label = "?"
            entities.append({"label": label, "value": r.get(metric, 0), "row": r})

    triggered = [e for e in entities if _cmp(e["value"], op, threshold)]
    if not triggered:
        return []

    sev = d.get("severity", "mid")
    priority = SEVERITY_PRIORITY.get(sev, "P1")
    dim = d.get("dimension")
    metric_name = METRIC_NAME.get(metric, metric)
    u = unit_of(metric)

    # 模板上下文
    entities_text = "；".join(f"{e['label']}={fmt_value(metric, e['value'])}" for e in triggered[:8])
    ctx = {
        "metric": metric_name, "metric_code": metric, "op": op, "op_sym": d.get("op_sym", op),
        "threshold": fmt_value(metric, threshold), "value": fmt_value(metric, triggered[0]["value"]),
        "scope": triggered[0]["label"], "scope_type": SCOPE_NAME.get(scope, scope),
        "dimension": DIMENSION_NAME.get(dim, dim), "entities": entities_text,
        "name": d.get("name", ""), "count": len(triggered),
    }
    advice = _safe_format(d.get("template", ""), ctx)

    title = (f"规则「{d.get('name', '自定义')}」命中：{metric_name} {d.get('op_sym', op)} "
             f"{fmt_value(metric, threshold)}")
    if scope != "account":
        title += f"（{len(triggered)} 个{SCOPE_NAME.get(scope, scope)}触发）"

    detail = (f"在 {scope == 'account' and '账户整体' or SCOPE_NAME.get(scope, scope)} 维度下，"
              f"满足「{metric_name} {d.get('op_sym', op)} {fmt_value(metric, threshold)}」的实体：{entities_text}"
              + (f" 等 {len(triggered)} 个" if len(triggered) > 8 else ""))

    mp = aggregate(db, shop_id, d1, d2, group_by="campaign")["summary"]
    return [{
        "dimension": dim, "priority": priority, "confidence": 0.72,
        "title": title,
        "detail": detail,
        "action": advice,
        "expected_impact": "依据自定义规则触发，请结合指标趋势评估调整后影响",
        "evidence": [{
            "metric_path": f"{scope}.{metric}[{op}{threshold}]",
            "snapshot": {"scope": scope, "metric": metric, "op": op, "threshold": threshold,
                         "triggered": [{"label": e["label"], "value": round(e["value"], 4)} for e in triggered[:20]],
                         "summary_acos": mp.get("acos"), "summary_sales": mp.get("sales")},
        }],
    }]


def dsl_meta():
    """供前端构建器使用的元数据。"""
    return {
        "metrics": [{"code": m["code"], "name_zh": m["name_zh"], "unit": unit_of(m["code"])} for m in METRICS],
        "ops": [{"sym": k, "label": OP_SYMBOL[k], "code": v} for k, v in OPS.items()],
        "scopes": [{"code": s, "name_zh": SCOPE_NAME[s]} for s in SCOPES],
        "dimensions": [{"code": d["code"], "name_zh": d["name_zh"]} for d in DIMENSIONS],
        "severities": [{"code": s, "priority": SEVERITY_PRIORITY[s]} for s in SEVERITIES],
    }
