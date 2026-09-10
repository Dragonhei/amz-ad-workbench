"""API 路由契约测试：验证鉴权、响应结构与错误码（T3 路由契约测试）。"""
import pytest
from datetime import date

from app.models import (FactAdPerf, FactSearchTerm, FactInventory, FactListingDaily,
                        FactAba, LlmProvider)


@pytest.fixture(autouse=True)
def clean_facts(db):
    for m in (FactAdPerf, FactSearchTerm, FactInventory, FactListingDaily, FactAba):
        db.query(m).delete()
    db.commit()
    yield


def _fact(db, **kw):
    base = dict(shop_id=1, date=date(2026, 3, 1), ad_format="SP", level="campaign",
                campaign_id="C1", campaign_name="C1", keyword_text="kw",
                impressions=1000, clicks=20, spend=50.0, orders=2, units=2, sales=200.0)
    base.update(kw)
    db.add(FactAdPerf(**base))
    db.commit()


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_bi_metrics(client):
    r = client.get("/api/bi/metrics")
    assert r.status_code == 200
    assert "items" in r.json()


def test_bi_shops_admin(client):
    r = client.get("/api/bi/shops")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 3
    assert items[0]["marketplace"] == "US"
    assert "currency" in items[0] and "timezone" in items[0]


def test_bi_shops_operator_scope(client):
    r = client.get("/api/bi/shops", headers={"X-Username": "operator"})
    assert r.status_code == 200
    assert [s["id"] for s in r.json()["items"]] == [1]


def test_operator_forbidden_other_shop(client):
    r = client.get("/api/inventory?shop_id=2", headers={"X-Username": "operator"})
    assert r.status_code == 403


def test_bi_range(client):
    r = client.get("/api/bi/range")
    assert r.status_code == 200
    assert "start" in r.json() and "end" in r.json()


def test_bi_query_with_data(client, db):
    _fact(db)
    r = client.get("/api/bi/query?group_by=campaign")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    assert body["rows"][0]["spend"] == 50.0


def test_bi_overview(client, db):
    _fact(db)
    r = client.get("/api/bi/overview?days=30")
    assert r.status_code == 200
    assert "delta" in r.json()


def test_bi_trend(client, db):
    _fact(db)
    r = client.get("/api/bi/trend")
    assert r.status_code == 200
    assert "points" in r.json()


def test_bi_drill_campaign(client, db):
    _fact(db)
    r = client.get("/api/bi/drill?campaign_id=C1")
    assert r.status_code == 200
    assert r.json()["level"] == "adgroup"


def test_inventory_with_data(client, db):
    db.add(FactInventory(shop_id=1, date=date(2026, 3, 1), asin="B0X1", sku="S1",
                         qty=100, inbound=0, days_of_cover=30))
    db.add(FactListingDaily(shop_id=1, date=date(2026, 3, 1), asin="B0X1", units=2))
    db.commit()
    r = client.get("/api/inventory")
    assert r.status_code == 200
    assert r.json()["summary"]["asin_count"] >= 1


def test_analysis_providers(client):
    r = client.get("/api/analysis/providers")
    assert r.status_code == 200
    assert len(r.json()["items"]) >= 1


def test_analysis_rules_list(client):
    r = client.get("/api/analysis/rules")
    assert r.status_code == 200
    codes = [x["code"] for x in r.json()["items"]]
    assert "high_spend_zero_order" in codes


def test_analysis_dimensions(client):
    r = client.get("/api/analysis/dimensions")
    assert r.status_code == 200
    assert len(r.json()["items"]) == 12


def test_dsl_validate_ok(client):
    r = client.get("/api/analysis/dsl/validate",
                   params={"text": 'WHEN acos > 10 FOR campaign THEN SUGGEST bid "x"'})
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_dsl_validate_bad(client):
    r = client.get("/api/analysis/dsl/validate", params={"text": "NOT A DSL"})
    assert r.status_code == 200
    assert r.json()["ok"] is False


def test_rule_crud(client):
    r = client.post("/api/analysis/rules", json={
        "code": "ut_rule_1", "name_zh": "UT规则", "dimension": "bid",
        "dsl_text": "WHEN acos > 10 FOR campaign THEN SUGGEST bid 'x'"})
    assert r.status_code == 200
    rid = r.json()["id"]
    r = client.put(f"/api/analysis/rules/{rid}", json={"id": rid, "enabled": False})
    assert r.status_code == 200
    r = client.delete(f"/api/analysis/rules/{rid}")
    assert r.status_code == 200


def test_analysis_run_rule_mode(client, db):
    _fact(db)
    r = client.post("/api/analysis/run",
                    json={"shop_id": 1, "use_llm": False, "target_acos": 35.0})
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "rule"
    assert "items" in body
    assert body["run_id"] is not None


def test_analysis_run_operator_forbidden(client, db):
    _fact(db)
    r = client.post("/api/analysis/run",
                    json={"shop_id": 2, "use_llm": False},
                    headers={"X-Username": "operator"})
    assert r.status_code == 403


def test_analysis_run_compare(client, db):
    _fact(db)
    mocks = db.query(LlmProvider).filter(LlmProvider.endpoint == "mock://").all()
    assert len(mocks) >= 2
    r = client.post("/api/analysis/run",
                    json={"shop_id": 1, "use_llm": True,
                          "provider_ids": [m.id for m in mocks]})
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "compare"
    assert len(body["results"]) >= 2


def test_provider_test_mock(client, db):
    mock = db.query(LlmProvider).filter(LlmProvider.endpoint == "mock://").first()
    assert mock is not None
    r = client.post(f"/api/analysis/providers/{mock.id}/test")
    assert r.status_code == 200
    assert r.json()["ok"] is True
