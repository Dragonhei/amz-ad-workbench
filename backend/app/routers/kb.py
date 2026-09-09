"""知识库：关键词库 / CPC 竞价库 / 排名追踪 / 竞品库，含批量导入导出与变更记录。"""
import csv
import io
import json
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import current_user
from ..db import get_db
from ..models import (FactAba, KbBidRule, KbChangeLog, KbCompetitor, KbKeyword, KbRankTrack, User)

router = APIRouter(prefix="/api/kb", tags=["kb"])

ENTITIES = {
    "keyword": (KbKeyword, ["id", "term", "intent", "relevance", "status", "asin", "note"]),
    "bid": (KbBidRule, ["id", "keyword", "match_type", "placement", "base_cpc", "min_cpc",
                        "max_cpc", "step", "note"]),
    "rank": (KbRankTrack, ["id", "asin", "term", "marketplace", "rank_source", "track_date",
                           "organic_rank", "ad_rank", "page"]),
    "competitor": (KbCompetitor, ["id", "competitor_asin", "brand", "price", "rating", "reviews",
                                  "selling_points", "note"]),
}


def _log(db, shop_id, entity, eid, field, old, new, operator):
    if str(old) == str(new):
        return
    db.add(KbChangeLog(shop_id=shop_id, entity=entity, entity_id=eid, field=field,
                       old_value=str(old or ""), new_value=str(new or ""), operator=operator))


def _row(model, r, fields):
    d = {}
    for f in fields:
        v = getattr(r, f)
        d[f] = v.isoformat() if isinstance(v, (date, datetime)) else v
    return d


def _rank_delta(rows):
    """为每条排名记录附加 `delta_organic`：与 10 天内最近一次环比（正数=排名下跌/变差）。"""
    by_key = {}
    for r in rows:
        by_key.setdefault((r.asin, r.term, r.marketplace), []).append(r)
    delta = {}
    for key, recs in by_key.items():
        recs.sort(key=lambda x: x.track_date)
        for i, r in enumerate(recs):
            prev = None
            for j in range(i - 1, -1, -1):
                if 0 < (r.track_date - recs[j].track_date).days <= 10:
                    prev = recs[j]
                    break
            if prev and r.organic_rank and prev.organic_rank:
                delta[(key, r.track_date)] = r.organic_rank - prev.organic_rank
    return delta


def _list(entity, shop_id, db):
    model, fields = ENTITIES[entity]
    q = db.query(model)
    if hasattr(model, "shop_id"):
        q = q.filter(model.shop_id.in_([shop_id, 0]))
    rows = q.order_by(model.id.desc()).limit(2000).all()
    items = [_row(model, r, fields) for r in rows]
    if entity == "rank":
        delta = _rank_delta(rows)
        # 仅最新一条标注 delta（按 key 找最新 track_date）
        latest_date = {}
        for r in rows:
            key = (r.asin, r.term, r.marketplace)
            if key not in latest_date or r.track_date > latest_date[key]:
                latest_date[key] = r.track_date
        by_id = {it["id"]: it for it in items}
        for r in rows:
            key = (r.asin, r.term, r.marketplace)
            if latest_date[key] == r.track_date and (key, r.track_date) in delta:
                by_id[r.id]["delta_organic"] = delta[(key, r.track_date)]
    return {"items": items, "fields": fields}


class ImportIn(BaseModel):
    entity: str
    shop_id: int = 1
    rows: list
    mode: str = "append"          # append | replace


@router.post("/import")            # 必须注册在 /{entity} 之前，否则会被动态路由吞掉
def import_rows(body: ImportIn, db: Session = Depends(get_db), u: User = Depends(current_user)):
    if body.entity not in ENTITIES:
        raise HTTPException(404, "未知知识库类型")
    model, fields = ENTITIES[body.entity]
    if body.mode == "replace":
        db.query(model).filter(model.shop_id == body.shop_id).delete()
    ok, fail = 0, []
    for i, row in enumerate(body.rows):
        try:
            obj = model()
            for f in fields:
                if f == "id" or f not in row:
                    continue
                v = row[f]
                if f in ("base_cpc", "min_cpc", "max_cpc", "step", "price", "rating"):
                    v = float(v or 0)
                elif f in ("reviews", "organic_rank", "ad_rank", "page"):
                    v = int(v or 0)
                elif f in ("track_date",) and isinstance(v, str) and v:
                    v = date.fromisoformat(v)
                setattr(obj, f, v)
            if hasattr(model, "shop_id"):
                obj.shop_id = body.shop_id
            if hasattr(model, "updated_by"):
                obj.updated_by = u.username
            db.add(obj)
            ok += 1
        except Exception as e:                                # noqa: BLE001
            fail.append({"row": i + 1, "message": f"{type(e).__name__}: {str(e)[:120]}"})
    _log(db, body.shop_id, body.entity, 0, "import", "", f"导入 {ok} 条，失败 {len(fail)} 条", u.username)
    db.commit()
    return {"ok": True, "inserted": ok, "failed": fail}


@router.get("/{entity}")
def list_entity(entity: str, shop_id: int = 1, db: Session = Depends(get_db),
                u: User = Depends(current_user)):
    if entity not in ENTITIES:
        raise HTTPException(404, "未知知识库类型")
    return _list(entity, shop_id, db)


@router.post("/{entity}")
def create_entity(entity: str, payload: dict, shop_id: int = 1,
                  db: Session = Depends(get_db), u: User = Depends(current_user)):
    model, fields = ENTITIES[entity]
    obj = model()
    for f in fields:
        if f in ("id",) or f not in payload:
            continue
        v = payload[f]
        if f in ("track_date",) and isinstance(v, str) and v:
            v = date.fromisoformat(v)
        setattr(obj, f, v)
    if hasattr(model, "shop_id"):
        obj.shop_id = shop_id
    if hasattr(model, "updated_by"):
        obj.updated_by = u.username
    db.add(obj)
    db.commit()
    _log(db, shop_id, entity, obj.id, "create", "", json.dumps(payload, ensure_ascii=False)[:500], u.username)
    db.commit()
    return {"ok": True, "id": obj.id}


@router.put("/{entity}/{eid}")
def update_entity(entity: str, eid: int, payload: dict, db: Session = Depends(get_db),
                  u: User = Depends(current_user)):
    model, fields = ENTITIES[entity]
    obj = db.query(model).get(eid)
    if not obj:
        raise HTTPException(404, "记录不存在")
    for f in fields:
        if f == "id" or f not in payload:
            continue
        old = getattr(obj, f)
        v = payload[f]
        if f in ("track_date",) and isinstance(v, str) and v:
            v = date.fromisoformat(v)
        setattr(obj, f, v)
        _log(db, getattr(obj, "shop_id", 0), entity, eid, f, old, v, u.username)
    if hasattr(model, "updated_by"):
        obj.updated_by = u.username
    db.commit()
    return {"ok": True}


@router.delete("/{entity}/{eid}")
def delete_entity(entity: str, eid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    model, _ = ENTITIES[entity]
    obj = db.query(model).get(eid)
    if not obj:
        raise HTTPException(404, "记录不存在")
    _log(db, getattr(obj, "shop_id", 0), entity, eid, "delete", "", "已删除", u.username)
    db.delete(obj)
    db.commit()
    return {"ok": True}


@router.get("/{entity}/export")
def export_entity(entity: str, shop_id: int = 1, db: Session = Depends(get_db),
                  u: User = Depends(current_user)):
    data = _list(entity, shop_id, db)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=data["fields"])
    w.writeheader()
    for r in data["items"]:
        w.writerow({k: r.get(k, "") for k in data["fields"]})
    return Response(content="\ufeff" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename={entity}.csv"})


@router.get("/rank/trend")
def rank_trend(shop_id: int = 1, marketplace: str = "", asin: str = "", term: str = "",
               limit: int = 50, db: Session = Depends(get_db),
               u: User = Depends(current_user)):
    """排名趋势时间序列：按 (asin, term, marketplace) 分组，附最新一周环比 delta 与掉落预警。"""
    q = db.query(KbRankTrack).filter(KbRankTrack.shop_id.in_([shop_id, 0]))
    if marketplace:
        q = q.filter(KbRankTrack.marketplace == marketplace)
    if asin:
        q = q.filter(KbRankTrack.asin == asin)
    if term:
        q = q.filter(KbRankTrack.term == term)
    rows = q.order_by(KbRankTrack.asin, KbRankTrack.term,
                     KbRankTrack.marketplace, KbRankTrack.track_date).all()

    groups = {}
    for r in rows:
        groups.setdefault((r.asin, r.term, r.marketplace), []).append(r)
    series, drops = [], []
    for (asin_, term_, mp), recs in groups.items():
        recs.sort(key=lambda x: x.track_date)
        points = [{
            "date": (x.track_date.isoformat() if isinstance(x.track_date, (date, datetime))
                     else str(x.track_date)),
            "organic_rank": x.organic_rank, "ad_rank": x.ad_rank, "page": x.page,
        } for x in recs]
        latest = recs[-1]
        prev = None
        for x in recs[:-1]:
            if 0 < (latest.track_date - x.track_date).days <= 10:
                prev = x
        delta = (latest.organic_rank - prev.organic_rank) if (prev and latest.organic_rank
                                                              and prev.organic_rank) else None
        series.append({
            "asin": asin_, "term": term_, "marketplace": mp,
            "rank_source": latest.rank_source, "points": points,
            "latest_organic": latest.organic_rank, "prev_organic": prev.organic_rank if prev else None,
            "delta": delta,
        })
        if delta is not None and delta >= 3:
            drops.append({"asin": asin_, "term": term_, "marketplace": mp,
                          "latest": latest.organic_rank, "prev": prev.organic_rank, "delta": delta})
    # 有掉落的系列优先展示
    series.sort(key=lambda s: (s["delta"] is not None and s["delta"] >= 3, s["delta"] or 0), reverse=True)
    return {"series": series[:limit], "drops": drops, "total_series": len(series)}


@router.get("/aba/terms")
def aba_terms(shop_id: int = 1, limit: int = 30, db: Session = Depends(get_db),
              u: User = Depends(current_user)):
    """返回店铺内 ABA 高潜搜索词，供一键加入排名追踪。"""
    rows = (db.query(FactAba).filter(FactAba.shop_id == shop_id)
            .order_by(FactAba.search_rank).limit(limit).all())
    return {"items": [{
        "term": a.search_term, "search_rank": a.search_rank,
        "top3_click_share": a.top3_click_share, "top3_conv_share": a.top3_conv_share,
    } for a in rows]}


class RankFromAbaIn(BaseModel):
    shop_id: int = 1
    asin: str = ""
    term: str
    marketplace: str = "US"
    rank_source: str = "aba"


@router.post("/rank/from-aba")
def rank_from_aba(body: RankFromAbaIn, db: Session = Depends(get_db),
                  u: User = Depends(current_user)):
    """从 ABA 高潜词一键新建排名追踪记录（默认排名留空，待回填实测值）。"""
    obj = KbRankTrack(shop_id=body.shop_id, asin=body.asin, term=body.term,
                      marketplace=body.marketplace, rank_source=body.rank_source,
                      track_date=date.today(), organic_rank=0, ad_rank=0, page=1)
    db.add(obj)
    db.commit()
    _log(db, body.shop_id, "rank", obj.id, "create", "",
         f"从 ABA 词 {body.term} 加入排名追踪", u.username)
    db.commit()
    return {"ok": True, "id": obj.id}


@router.get("/changes/log")
def change_log(entity: str = "", shop_id: int = 1, limit: int = 200,
               db: Session = Depends(get_db), u: User = Depends(current_user)):
    q = db.query(KbChangeLog).filter(KbChangeLog.shop_id.in_([shop_id, 0]))
    if entity:
        q = q.filter(KbChangeLog.entity == entity)
    rows = q.order_by(KbChangeLog.id.desc()).limit(limit).all()
    return {"items": [{"id": r.id, "entity": r.entity, "entity_id": r.entity_id, "field": r.field,
                       "old_value": r.old_value, "new_value": r.new_value, "operator": r.operator,
                       "created_at": r.created_at.strftime("%Y-%m-%d %H:%M")} for r in rows]}
