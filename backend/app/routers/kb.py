"""知识库：关键词库 / CPC 竞价库 / 排名追踪 / 竞品库，含批量导入导出与变更记录。"""
import csv
import io
import json
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import current_user
from ..db import get_db
from ..models import (KbBidRule, KbChangeLog, KbCompetitor, KbKeyword, KbRankTrack, User)

router = APIRouter(prefix="/api/kb", tags=["kb"])

ENTITIES = {
    "keyword": (KbKeyword, ["id", "term", "intent", "relevance", "status", "asin", "note"]),
    "bid": (KbBidRule, ["id", "keyword", "match_type", "placement", "base_cpc", "min_cpc",
                        "max_cpc", "step", "note"]),
    "rank": (KbRankTrack, ["id", "asin", "term", "track_date", "organic_rank", "ad_rank", "page"]),
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


def _list(entity, shop_id, db):
    model, fields = ENTITIES[entity]
    q = db.query(model)
    if hasattr(model, "shop_id"):
        q = q.filter(model.shop_id.in_([shop_id, 0]))
    rows = q.order_by(model.id.desc()).limit(2000).all()
    return {"items": [_row(model, r, fields) for r in rows], "fields": fields}


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
