"""鉴权模块单测：密码哈希、当前用户解析、店铺权限矩阵。"""
import pytest
from fastapi import HTTPException

from app.auth import (hash_password, current_user, assert_shop_access,
                      shop_ids_of, require_admin)
from app.models import User


def test_hash_password_deterministic():
    h1 = hash_password("secret")
    assert h1 == hash_password("secret")
    assert hash_password("other") != h1
    assert "secret" not in h1


def test_current_user_admin(db):
    u = current_user(username="admin", db=db)
    assert u is not None and u.role == "admin"


def test_current_user_disabled_raises(db):
    u = User(username="disabled1", password_hash=hash_password("x"),
             role="operator", status="disabled")
    db.add(u)
    db.commit()
    db.refresh(u)
    with pytest.raises(HTTPException) as e:
        current_user(username="disabled1", db=db)
    assert e.value.status_code == 403


def test_shop_ids_of_admin_is_unrestricted(db):
    admin = current_user(username="admin", db=db)
    assert shop_ids_of(admin) is None


def test_assert_shop_access_admin_passes_everywhere(db):
    admin = current_user(username="admin", db=db)
    assert_shop_access(admin, 999)  # 无异常


def test_assert_shop_access_denied_for_other_shop(db):
    u = User(username="staff_auth1", password_hash=hash_password("x"),
             role="operator", status="active", allowed_shop_ids="[2]")
    db.add(u)
    db.commit()
    db.refresh(u)
    with pytest.raises(HTTPException) as e:
        assert_shop_access(u, 1)
    assert e.value.status_code == 403
    assert_shop_access(u, 2)  # 授权店铺不抛错


def test_require_admin_gates_operator(db):
    op = User(username="staff_auth2", password_hash=hash_password("x"),
              role="operator", status="active")
    db.add(op)
    db.commit()
    db.refresh(op)
    with pytest.raises(HTTPException):
        require_admin(op)
    admin = current_user(username="admin", db=db)
    assert require_admin(admin) is admin


def test_shop_ids_of_operator(db):
    op = User(username="staff_auth3", password_hash=hash_password("x"),
              role="operator", status="active", allowed_shop_ids="[7, 8]")
    db.add(op)
    db.commit()
    db.refresh(op)
    assert shop_ids_of(op) == [7, 8]


def test_resolve_shop_ids_requested_intersection(db):
    from app.auth import resolve_shop_ids
    op = User(username="staff_auth4", password_hash=hash_password("x"),
              role="operator", status="active", allowed_shop_ids="[7, 8]")
    db.add(op)
    db.commit()
    db.refresh(op)
    assert resolve_shop_ids(op, [7]) == [7]  # 全部授权：原样返回
    with pytest.raises(HTTPException):        # 含越权店铺：整体 403，不做静默过滤
        resolve_shop_ids(op, [7, 9])


def test_resolve_shop_ids_denied(db):
    from app.auth import resolve_shop_ids
    op = User(username="staff_auth5", password_hash=hash_password("x"),
              role="operator", status="active", allowed_shop_ids="[7]")
    db.add(op)
    db.commit()
    db.refresh(op)
    with pytest.raises(HTTPException) as e:
        resolve_shop_ids(op, [99])
    assert e.value.status_code == 403


def test_my_shops_admin(db):
    from app.auth import my_shops
    admin = current_user(username="admin", db=db)
    shops = my_shops(db, admin)
    assert isinstance(shops, list) and shops


def test_resolve_shop_ids_admin_variants(db):
    from app.auth import resolve_shop_ids
    admin = current_user(username="admin", db=db)
    # admin + 指定请求：直接返回请求列表
    assert resolve_shop_ids(admin, [3, 4]) == [3, 4]
    # admin + 无请求：返回系统内全部店铺
    assert isinstance(resolve_shop_ids(admin), list) and resolve_shop_ids(admin)


def test_shop_ids_of_bad_json_returns_empty(db):
    op = User(username="staff_auth6", password_hash=hash_password("x"),
              role="operator", status="active", allowed_shop_ids="not-json")
    db.add(op)
    db.commit()
    db.refresh(op)
    assert shop_ids_of(op) == []
