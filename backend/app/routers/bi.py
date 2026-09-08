"""BI 看板：全指标筛选、排序、下钻、趋势与环比。"""
import json
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth import assert_shop_access, current_user
from ..db import get_db
from ..metrics import METRICS, aggregate, daily_trend, date_range_of
from ..models import FactAdPerf, User

router = APIRouter(prefix="/api/bi", tags=["bi"])


def _parse_filters(raw: str):
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except ValueError:
        return {}


@router.get("/metrics")
def metrics():
    return {"items": METRICS}


@router.get("/range")
def rng(shop_id: int = 1, db: Session = Depends(get_db), u: User = Depends(current_user)):
    d1, d2 = date_range_of(db, shop_id)
    return {"start": str(d1), "end": str(d2)}


@router.get("/campaigns")
def campaigns(shop_id: int = 1, db: Session = Depends(get_db), u: User = Depends(current_user)):
    rows = (db.query(FactAdPerf.campaign_id, FactAdPerf.campaign_name)
            .filter(FactAdPerf.shop_id == shop_id).distinct().all())
    return {"items": [{"id": r[0] or "", "name": r[1] or "(未命名活动)"} for r in rows]}


@router.get("/query")
def query(shop_id: int = 1, start: str = "", end: str = "", group_by: str = "campaign",
          filters: str = "", sort_by: str = "spend", sort_dir: str = "desc",
          page: int = 1, size: int = 100,
          db: Session = Depends(get_db), u: User = Depends(current_user)):
    assert_shop_access(u, shop_id)
    d1 = date.fromisoformat(start) if start else None
    d2 = date.fromisoformat(end) if end else None
    if not (d1 and d2):
        _a, _b = date_range_of(db, shop_id)
        d1, d2 = d1 or _a, d2 or _b
    res = aggregate(db, shop_id, d1, d2, group_by, _parse_filters(filters), sort_by, sort_dir,
                    limit=size, offset=(page - 1) * size)
    return {"rows": res["rows"], "total": res["total"], "summary": res["summary"],
            "total_sales": res["total_sales"], "group_by": group_by}


@router.get("/trend")
def trend(shop_id: int = 1, start: str = "", end: str = "", filters: str = "",
          db: Session = Depends(get_db), u: User = Depends(current_user)):
    d1 = date.fromisoformat(start) if start else None
    d2 = date.fromisoformat(end) if end else None
    if not (d1 and d2):
        _a, _b = date_range_of(db, shop_id)
        d1, d2 = d1 or _a, d2 or _b
    res = daily_trend(db, shop_id, d1, d2, _parse_filters(filters))
    return res


@router.get("/overview")
def overview(shop_id: int = 1, days: int = 30, db: Session = Depends(get_db),
             u: User = Depends(current_user)):
    d2 = date_range_of(db, shop_id)[1] or date.today()
    d1 = d2 - timedelta(days=days - 1)
    cur = aggregate(db, shop_id, d1, d2, group_by="campaign")["summary"]
    p1 = d1 - timedelta(days=1)
    prev = aggregate(db, shop_id, p1 - timedelta(days=days - 1), p1, group_by="campaign")["summary"]
    def delta(a, b):
        return round((a - b) / b * 100, 2) if b else None
    return {
        "period": [str(d1), str(d2)],
        "current": cur,
        "previous": prev,
        "delta": {k: delta(cur.get(k, 0), prev.get(k, 0)) for k in
                  ("spend", "sales", "acos", "tacos", "orders", "ctr", "cvr", "cpc", "clicks")},
    }


@router.get("/drill")
def drill(shop_id: int = 1, start: str = "", end: str = "", campaign_id: str = "",
          adgroup_id: str = "", db: Session = Depends(get_db), u: User = Depends(current_user)):
    """层级下钻：活动 → 广告组 → 关键词。"""
    d1 = date.fromisoformat(start) if start else None
    d2 = date.fromisoformat(end) if end else None
    f = {"campaign_ids": [campaign_id]} if campaign_id else {}
    if campaign_id and adgroup_id:
        rows = (db.query(FactAdPerf.keyword_text, FactAdPerf.match_type,
                         func.sum(FactAdPerf.impressions), func.sum(FactAdPerf.clicks),
                         func.sum(FactAdPerf.spend), func.sum(FactAdPerf.orders),
                         func.sum(FactAdPerf.sales))
                .filter(FactAdPerf.shop_id == shop_id, FactAdPerf.campaign_id == campaign_id,
                        FactAdPerf.adgroup_id == adgroup_id))
        if d1:
            rows = rows.filter(FactAdPerf.date >= d1)
        if d2:
            rows = rows.filter(FactAdPerf.date <= d2)
        rows = rows.group_by(FactAdPerf.keyword_text, FactAdPerf.match_type).all()
        from ..metrics import calc_metrics, period_totals
        ts = period_totals(db, shop_id, d1, d2)
        out = [{"keyword_text": r[0], "match_type": r[1],
                **calc_metrics(int(r[2] or 0), int(r[3] or 0), float(r[4] or 0),
                               int(r[5] or 0), float(r[6] or 0), ts)} for r in rows]
        return {"level": "keyword", "rows": out}
    if campaign_id:
        rows = (db.query(FactAdPerf.adgroup_id, FactAdPerf.adgroup_name,
                         func.sum(FactAdPerf.impressions), func.sum(FactAdPerf.clicks),
                         func.sum(FactAdPerf.spend), func.sum(FactAdPerf.orders),
                         func.sum(FactAdPerf.sales))
                .filter(FactAdPerf.shop_id == shop_id, FactAdPerf.campaign_id == campaign_id))
        if d1:
            rows = rows.filter(FactAdPerf.date >= d1)
        if d2:
            rows = rows.filter(FactAdPerf.date <= d2)
        rows = rows.group_by(FactAdPerf.adgroup_id, FactAdPerf.adgroup_name).all()
        from ..metrics import calc_metrics, period_totals
        ts = period_totals(db, shop_id, d1, d2)
        out = [{"adgroup_id": r[0], "adgroup_name": r[1],
                **calc_metrics(int(r[2] or 0), int(r[3] or 0), float(r[4] or 0),
                               int(r[5] or 0), float(r[6] or 0), ts)} for r in rows]
        return {"level": "adgroup", "rows": out}
    return {"level": "campaign",
            "rows": aggregate(db, shop_id, d1, d2, group_by="campaign")["rows"]}
