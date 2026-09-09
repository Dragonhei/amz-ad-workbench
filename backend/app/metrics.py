"""统一指标口径与聚合查询。"""
from datetime import date, timedelta

from sqlalchemy import func

from .models import FactAdPerf, FactListingDaily


METRICS = [
    {"code": "impressions", "name_zh": "曝光量", "unit": "", "higher_better": True,
     "formula": "sum(impressions)"},
    {"code": "clicks", "name_zh": "点击量", "unit": "", "higher_better": True, "formula": "sum(clicks)"},
    {"code": "ctr", "name_zh": "点击率 CTR", "unit": "%", "higher_better": True, "formula": "clicks / impressions"},
    {"code": "cpc", "name_zh": "单次点击成本", "unit": "", "higher_better": False, "formula": "spend / clicks"},
    {"code": "spend", "name_zh": "广告花费", "unit": "", "higher_better": False, "formula": "sum(spend)"},
    {"code": "orders", "name_zh": "广告订单", "unit": "", "higher_better": True, "formula": "sum(orders)"},
    {"code": "cvr", "name_zh": "转化率 CVR", "unit": "%", "higher_better": True, "formula": "orders / clicks"},
    {"code": "sales", "name_zh": "广告销售额", "unit": "", "higher_better": True, "formula": "sum(sales)"},
    {"code": "acos", "name_zh": "ACOS", "unit": "%", "higher_better": False, "formula": "spend / sales"},
    {"code": "roas", "name_zh": "ROAS", "unit": "", "higher_better": True, "formula": "sales / spend"},
    {"code": "tacos", "name_zh": "TACOS", "unit": "%", "higher_better": False, "formula": "spend / 总销售额"},
]

GROUP_FIELDS = {
    "date": ("date",),
    "campaign": ("campaign_id", "campaign_name"),
    "adgroup": ("adgroup_id", "adgroup_name"),
    "keyword": ("keyword_text", "match_type"),
    "ad_format": ("ad_format",),
    "placement": ("placement",),
    "targeting": ("targeting",),
}


def _shop_ids(s):
    """归一化为店铺 id 列表；None 表示不过滤（全部店铺）。"""
    if s is None:
        return None
    if isinstance(s, int):
        return [s]
    return [int(x) for x in s]


def calc_metrics(imp, clk, spend, orders, sales, total_sales=0.0):
    ctr = (clk / imp * 100) if imp else 0.0
    cvr = (orders / clk * 100) if clk else 0.0
    cpc = (spend / clk) if clk else 0.0
    acos = (spend / sales * 100) if sales else 0.0
    roas = (sales / spend) if spend else 0.0
    tacos = (spend / total_sales * 100) if total_sales else 0.0
    return {
        "impressions": imp, "clicks": clk, "ctr": round(ctr, 3), "cpc": round(cpc, 3),
        "spend": round(spend, 2), "orders": orders, "cvr": round(cvr, 3),
        "sales": round(sales, 2), "acos": round(acos, 3), "roas": round(roas, 3),
        "tacos": round(tacos, 3),
    }


def period_totals(db, shop_ids, d1=None, d2=None):
    """店铺（可多个）在 [d1,d2] 的业务报告总销售额，用作 TACOS 分母；未给日期时取全量。"""
    sids = _shop_ids(shop_ids)
    q = db.query(func.sum(FactListingDaily.total_sales))
    if sids is not None:
        q = q.filter(FactListingDaily.shop_id.in_(sids))
    if d1:
        q = q.filter(FactListingDaily.date >= d1)
    if d2:
        q = q.filter(FactListingDaily.date <= d2)
    return float(q.scalar() or 0.0)


def aggregate(db, shop_ids, d1, d2, group_by="campaign", filters=None, sort_by="spend",
              sort_dir="desc", limit=500, offset=0):
    filters = filters or {}
    cols = GROUP_FIELDS.get(group_by, ("campaign_id", "campaign_name"))
    q = db.query(
        *[getattr(FactAdPerf, c).label(c) for c in cols],
        func.sum(FactAdPerf.impressions).label("impressions"),
        func.sum(FactAdPerf.clicks).label("clicks"),
        func.sum(FactAdPerf.spend).label("spend"),
        func.sum(FactAdPerf.orders).label("orders"),
        func.sum(FactAdPerf.units).label("units"),
        func.sum(FactAdPerf.sales).label("sales"),
    )
    sids = _shop_ids(shop_ids)
    if sids is not None:
        q = q.filter(FactAdPerf.shop_id.in_(sids))
    if d1:
        q = q.filter(FactAdPerf.date >= d1)
    if d2:
        q = q.filter(FactAdPerf.date <= d2)
    if filters.get("ad_format"):
        q = q.filter(FactAdPerf.ad_format == filters["ad_format"])
    if filters.get("placement"):
        q = q.filter(FactAdPerf.placement == filters["placement"])
    if filters.get("targeting"):
        q = q.filter(FactAdPerf.targeting.like(f"%{filters['targeting']}%"))
    if filters.get("campaign_ids"):
        q = q.filter(FactAdPerf.campaign_id.in_(filters["campaign_ids"]))
    if filters.get("keyword_contains"):
        q = q.filter(FactAdPerf.keyword_text.like(f"%{filters['keyword_contains']}%"))

    q = q.group_by(*[getattr(FactAdPerf, c) for c in cols])
    rows = q.all()
    total_sales = period_totals(db, shop_ids, d1, d2)

    out = []
    for r in rows:
        m = calc_metrics(int(r.impressions or 0), int(r.clicks or 0), float(r.spend or 0),
                         int(r.orders or 0), float(r.sales or 0), total_sales)
        if filters.get("min_clicks") and m["clicks"] < int(filters["min_clicks"]):
            continue
        if filters.get("min_spend") and m["spend"] < float(filters["min_spend"]):
            continue
        if filters.get("max_acos") and (m["acos"] > float(filters["max_acos"]) or m["sales"] == 0):
            continue
        key = {}
        for c in cols:
            key["date" if c == "date" else c] = str(getattr(r, c) or "")
        out.append({**key, **m})

    rev = (sort_dir or "desc").lower() == "desc"
    if out and sort_by in out[0]:
        out.sort(key=lambda x: (x.get(sort_by) or 0), reverse=rev)
    total_row = calc_metrics(sum(o["impressions"] for o in out), sum(o["clicks"] for o in out),
                             sum(o["spend"] for o in out), sum(o["orders"] for o in out),
                             sum(o["sales"] for o in out), total_sales)
    return {"rows": out[offset:offset + limit], "total": len(out), "summary": total_row,
            "total_sales": round(total_sales, 2)}


def daily_trend(db, shop_ids, d1, d2, filters=None):
    res = aggregate(db, shop_ids, d1, d2, group_by="date", filters=filters, limit=100000)
    rows = sorted(res["rows"], key=lambda x: x.get("date") or "")
    return {"points": rows, "summary": res["summary"]}


def date_range_of(db, shop_ids):
    sids = _shop_ids(shop_ids)
    q = db.query(func.min(FactAdPerf.date), func.max(FactAdPerf.date))
    if sids is not None:
        q = q.filter(FactAdPerf.shop_id.in_(sids))
    r = q.first()
    return (r[0], r[1]) if r and r[0] else (date.today() - timedelta(days=29), date.today())
