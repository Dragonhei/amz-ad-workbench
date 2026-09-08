"""多用户管理：账号、角色、数据权限、API 配额与用量统计、审计日志。"""
import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth import hash_password, require_admin
from ..db import get_db
from ..models import AuditLog, Org, Shop, UsageLog, User

router = APIRouter(prefix="/api/admin", tags=["admin"])


class LoginIn(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.username == body.username).first()
    if not u or u.password_hash != hash_password(body.password):
        raise HTTPException(401, "用户名或密码错误")
    if u.status != "active":
        raise HTTPException(403, "账号已停用")
    db.add(AuditLog(user_id=u.id, action="login", target=u.username))
    db.commit()
    shop_ids = json.loads(u.allowed_shop_ids or "[]") if u.role != "admin" else None
    return {"ok": True, "user": {"id": u.id, "username": u.username, "full_name": u.full_name,
                                 "role": u.role, "shop_ids": shop_ids,
                                 "quota_tokens": u.quota_tokens, "quota_cost": u.quota_cost}}


@router.get("/users")
def users(db: Session = Depends(get_db), u: User = Depends(require_admin)):
    rows = db.query(User).order_by(User.id).all()
    out = []
    for r in rows:
        used_t = db.query(func.sum(UsageLog.prompt_tokens + UsageLog.completion_tokens)).filter(
            UsageLog.user_id == r.id).scalar() or 0
        used_c = db.query(func.sum(UsageLog.cost)).filter(UsageLog.user_id == r.id).scalar() or 0
        out.append({"id": r.id, "username": r.username, "full_name": r.full_name, "role": r.role,
                    "status": r.status, "shop_ids": json.loads(r.allowed_shop_ids or "[]"),
                    "quota_tokens": r.quota_tokens, "quota_cost": r.quota_cost,
                    "used_tokens": int(used_t), "used_cost": round(float(used_c), 4),
                    "created_at": r.created_at.strftime("%Y-%m-%d %H:%M")})
    return {"items": out}


class UserIn(BaseModel):
    id: int | None = None
    username: str
    password: str = ""
    full_name: str = ""
    role: str = "operator"
    status: str = "active"
    shop_ids: list = []
    quota_tokens: int = 2_000_000
    quota_cost: float = 200.0


@router.post("/users")
def save_user(body: UserIn, db: Session = Depends(get_db), u: User = Depends(require_admin)):
    obj = db.query(User).get(body.id) if body.id else None
    if not obj:
        if db.query(User).filter(User.username == body.username).first():
            raise HTTPException(400, "用户名已存在")
        obj = User(username=body.username, password_hash=hash_password(body.password or "123456"))
    else:
        if body.password:
            obj.password_hash = hash_password(body.password)
    obj.full_name = body.full_name
    obj.role = body.role
    obj.status = body.status
    obj.allowed_shop_ids = json.dumps(body.shop_ids)
    obj.quota_tokens = body.quota_tokens
    obj.quota_cost = body.quota_cost
    db.add(obj)
    db.commit()
    db.add(AuditLog(user_id=u.id, action="save_user", target=body.username,
                    detail=json.dumps({"role": body.role, "shop_ids": body.shop_ids},
                                      ensure_ascii=False)))
    db.commit()
    return {"ok": True, "id": obj.id}


@router.delete("/users/{uid}")
def del_user(uid: int, db: Session = Depends(get_db), u: User = Depends(require_admin)):
    obj = db.query(User).get(uid)
    if not obj:
        raise HTTPException(404, "用户不存在")
    if obj.username == "admin":
        raise HTTPException(400, "内置管理员不可删除")
    db.delete(obj)
    db.commit()
    return {"ok": True}


@router.get("/shops")
def shops(db: Session = Depends(get_db), u: User = Depends(require_admin)):
    rows = db.query(Shop).order_by(Shop.id).all()
    return {"items": [{"id": r.id, "name": r.name, "marketplace": r.marketplace,
                       "currency": r.currency, "timezone": r.timezone} for r in rows]}


class ShopIn(BaseModel):
    name: str
    marketplace: str = "US"
    currency: str = "USD"
    timezone: str = "America/New_York"


@router.post("/shops")
def create_shop(body: ShopIn, db: Session = Depends(get_db), u: User = Depends(require_admin)):
    s = Shop(name=body.name, marketplace=body.marketplace, currency=body.currency,
             timezone=body.timezone)
    db.add(s)
    db.commit()
    return {"ok": True, "id": s.id}


@router.get("/usage")
def usage(days: int = 30, db: Session = Depends(get_db), u: User = Depends(require_admin)):
    since = datetime.utcnow() - timedelta(days=days)
    by_user = (db.query(User.username, func.count(UsageLog.id),
                        func.sum(UsageLog.prompt_tokens + UsageLog.completion_tokens),
                        func.sum(UsageLog.cost))
               .outerjoin(UsageLog, (UsageLog.user_id == User.id) & (UsageLog.ts >= since))
               .group_by(User.id).all())
    daily = (db.query(func.date(UsageLog.ts).label("d"), func.count(UsageLog.id),
                      func.sum(UsageLog.prompt_tokens + UsageLog.completion_tokens),
                      func.sum(UsageLog.cost))
             .filter(UsageLog.ts >= since).group_by("d").all())
    recent = (db.query(UsageLog).order_by(UsageLog.id.desc()).limit(50).all())
    return {
        "by_user": [{"username": r[0], "calls": int(r[1] or 0), "tokens": int(r[2] or 0),
                     "cost": round(float(r[3] or 0), 4)} for r in by_user],
        "daily": [{"date": str(r[0]), "calls": int(r[1] or 0), "tokens": int(r[2] or 0),
                   "cost": round(float(r[3] or 0), 4)} for r in daily],
        "recent": [{"id": r.id, "user_id": r.user_id, "ts": r.ts.strftime("%Y-%m-%d %H:%M"),
                    "provider": r.provider, "model": r.model,
                    "tokens": (r.prompt_tokens or 0) + (r.completion_tokens or 0),
                    "cost": r.cost, "status": r.status, "message": r.message} for r in recent],
    }


@router.get("/audit")
def audit(limit: int = 100, db: Session = Depends(get_db), u: User = Depends(require_admin)):
    rows = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(limit).all()
    return {"items": [{"id": r.id, "ts": r.ts.strftime("%Y-%m-%d %H:%M"), "user_id": r.user_id,
                       "action": r.action, "target": r.target, "detail": r.detail} for r in rows]}
