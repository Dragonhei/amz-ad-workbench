"""库存看板：最新库存快照、低库存预警、在投联动标识（P1-6 库存联动预警）。"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..auth import current_user, my_shops, resolve_shop_ids
from ..db import get_db
from ..models import FactAdPerf, FactInventory, FactListingDaily, User

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


def _safe_div(a, b):
    return (a / b) if b else 0.0


def _resolve(db: Session, u: User, shop_id=None, marketplace: str = ""):
    """复用鉴权感知的店铺解析：admin = 全部，越权即抛 403。"""
    sids = resolve_shop_ids(u, requested=shop_id)
    if not sids:
        return []
    if marketplace:
        mp = {s["id"]: s.get("marketplace") for s in my_shops(db, u)}
        sids = [s for s in sids if mp.get(s) == marketplace]
    return sids


@router.get("")
def inventory(shop_id: Optional[list[int]] = Query(default=None),
             marketplace: str = "", threshold: float = 14.0,
             db: Session = Depends(get_db), u: User = Depends(current_user)):
    """返回每个 ASIN 的最新库存快照、可售天数、低库存与在投标识，以及汇总。"""
    sids = _resolve(db, u, shop_id, marketplace)
    if not sids:
        return {"items": [], "summary": {"asin_count": 0, "low_count": 0, "advertised_low": 0,
                                         "threshold": threshold}}
    rows = db.query(FactInventory).filter(FactInventory.shop_id.in_(sids)).all()
    if not rows:
        return {"items": [], "summary": {"asin_count": 0, "low_count": 0, "advertised_low": 0,
                                         "threshold": threshold}}

    # 每个 (shop_id, asin) 取最近日期的快照
    latest = {}
    for r in rows:
        key = (r.shop_id, r.asin)
        if key not in latest or r.date > latest[key].date:
            latest[key] = r
    dates = [r.date for r in rows]
    d1, d2 = min(dates), max(dates)
    num_days = max((d2 - d1).days + 1, 1)

    # 业务报告中的销量 → 推断该 ASIN 是否在售/在投
    ld = (db.query(FactListingDaily).filter(FactListingDaily.shop_id.in_(sids),
            FactListingDaily.date >= d1, FactListingDaily.date <= d2,
            FactListingDaily.asin != "").all())
    ld_units = {}
    for x in ld:
        ld_units[x.asin] = ld_units.get(x.asin, 0) + (x.units or 0)
    sd_asins = {a.associated_asin for a in db.query(FactAdPerf).filter(
        FactAdPerf.shop_id.in_(sids), FactAdPerf.associated_asin != "").all()}

    items, low_count, ad_low = [], 0, 0
    for (sid, asin), rec in latest.items():
        du = _safe_div(ld_units.get(asin, 0), num_days)
        cover = (rec.days_of_cover if (rec.days_of_cover or 0) > 0
                 else (_safe_div(rec.qty, du) if du else 0))
        advertised = (ld_units.get(asin, 0) > 0) or (asin in sd_asins)
        low = 0 < cover < threshold
        if low:
            low_count += 1
            if advertised:
                ad_low += 1
        items.append({
            "shop_id": sid, "asin": asin, "sku": rec.sku, "date": str(rec.date),
            "qty": rec.qty, "inbound": rec.inbound,
            "days_of_cover": round(cover, 1),
            "advertised": advertised, "low_stock": low,
        })
    items.sort(key=lambda x: x["days_of_cover"])
    return {
        "items": items,
        "summary": {
            "asin_count": len(items),
            "low_count": low_count,
            "advertised_low": ad_low,
            "threshold": threshold,
        },
    }
