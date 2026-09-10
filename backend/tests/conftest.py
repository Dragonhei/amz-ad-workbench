"""pytest 公共夹具：在导入 app 之前固定隔离数据库，提供 TestClient 与 DB 会话。"""
import os
import tempfile

# —— 必须在 import app 之前设置隔离数据库 ——
_DB_FILE = os.path.join(tempfile.gettempdir(), "amz_unit_test.db")
if os.path.exists(_DB_FILE):
    os.remove(_DB_FILE)
os.environ["DATABASE_URL"] = "sqlite:///" + _DB_FILE.replace("\\", "/")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import FactAdPerf  # noqa: E402


@pytest.fixture(scope="session")
def client():
    """触发 app.startup（建表 + 种子），提供 TestClient。"""
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db(client):
    """依赖 client（session 级，触发 startup 建表+种子），确保表已存在。"""
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def facts(db):
    """清空 fact_ad_perf 后交出一个干净的 db，测试结束再清空，保证数据隔离。"""
    db.query(FactAdPerf).delete()
    db.commit()
    yield db
    db.query(FactAdPerf).delete()
    db.commit()
