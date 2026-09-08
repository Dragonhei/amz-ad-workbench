"""极简鉴权：MVP 使用 X-Username 请求头标识操作者，生产应替换为 JWT/OAuth。"""
import hashlib

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .db import get_db
from .models import Shop, User


def hash_password(p: str) -> str:
    return hashlib.sha256(("amz::" + p).encode()).hexdigest()


def current_user(username: str = Header(default="admin", alias="X-Username"),
                 db: Session = Depends(get_db)) -> User:
    u = db.query(User).filter(User.username == username).first()
    if not u:
        u = db.query(User).order_by(User.id).first()
    if not u:
        raise HTTPException(status_code=401, detail="未找到用户")
    if u.status != "active":
        raise HTTPException(status_code=403, detail="账号已停用")
    return u


def require_admin(u: User = Depends(current_user)) -> User:
    if u.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return u


def shop_ids_of(u: User):
    import json
    if u.role == "admin":
        return None                       # None = 不限
    try:
        ids = json.loads(u.allowed_shop_ids or "[]")
    except ValueError:
        ids = []
    return ids


def assert_shop_access(u: User, shop_id: int):
    ids = shop_ids_of(u)
    if ids is None:
        return
    if int(shop_id) not in [int(i) for i in ids]:
        raise HTTPException(status_code=403, detail=f"无店铺 {shop_id} 的数据权限")


def resolve_shop_ids(u: User, requested=None):
    """返回当前用户实际可访问的店铺 id 列表。

    - requested 为空：返回用户被授权的全部店铺（admin 返回系统内全部）。
    - requested 给定：与授权集合求交集并逐店校验权限，越权即 403。
    """
    allowed = shop_ids_of(u)
    if requested:
        req = [int(x) for x in requested]
        if allowed is None:
            return req
        aset = set(int(i) for i in allowed)
        bad = [s for s in req if s not in aset]
        if bad:
            raise HTTPException(status_code=403, detail=f"无店铺 {bad} 的数据权限")
        return req
    if allowed is None:
        from .models import Shop
        from .db import SessionLocal
        d = SessionLocal()
        try:
            return [s.id for s in d.query(Shop.id).all()]
        finally:
            d.close()
    return [int(i) for i in allowed]


def my_shops(db: Session, u: User):
    """当前用户可访问的店铺清单（含 marketplace / currency / timezone）。"""
    ids = shop_ids_of(u)
    q = db.query(Shop)
    if ids is not None:
        q = q.filter(Shop.id.in_([int(i) for i in ids]))
    return [{"id": s.id, "name": s.name, "marketplace": s.marketplace,
             "currency": s.currency, "timezone": s.timezone} for s in q.all()]
