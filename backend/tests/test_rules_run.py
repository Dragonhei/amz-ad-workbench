"""规则引擎集成测试：构造受控事实数据，触发 run_rules 各分支（T3 规则覆盖率）。"""
import pytest
from datetime import date, timedelta

from app.rules import run_rules
from app.models import (FactAdPerf, FactSearchTerm, FactInventory, FactListingDaily,
                        FactAba)


@pytest.fixture(autouse=True)
def clean_facts(db):
    for m in (FactAdPerf, FactSearchTerm, FactInventory, FactListingDaily, FactAba):
        db.query(m).delete()
    db.commit()
    yield


D1 = date(2026, 1, 1)
D2 = date(2026, 1, 31)


def _add(db, **kw):
    base = dict(shop_id=1, date=D1, ad_format="SP", level="campaign",
                campaign_id="C1", campaign_name="C1", keyword_text="kw",
                impressions=1000, clicks=20, spend=50.0, orders=2, units=2, sales=200.0)
    base.update(kw)
    db.add(FactAdPerf(**base))


def _dims(items):
    return {it["dimension"] for it in items}


def test_negative_high_spend_zero_order(db):
    _add(db, keyword_text="badkw", campaign_id="C1", campaign_name="C1",
         spend=50.0, orders=0, clicks=30, impressions=3000)
    db.commit()
    items = run_rules(db, 1, D1, D2, 35.0)
    assert "negative" in _dims(items)
    assert any("零出单" in it["title"] for it in items if it["dimension"] == "negative")


def test_bid_acos_over_target(db):
    _add(db, campaign_id="CH", campaign_name="高ACOS", spend=300.0, sales=100.0,
         clicks=100, impressions=5000, orders=5)
    db.commit()
    items = run_rules(db, 1, D1, D2, 35.0)
    assert "bid" in _dims(items)


def test_budget_low_exposure_high_cvr(db):
    _add(db, keyword_text="goodkw", campaign_id="C2", campaign_name="C2",
         spend=20.0, sales=200.0, impressions=1000, clicks=10, orders=4)
    db.commit()
    items = run_rules(db, 1, D1, D2, 35.0)
    assert "budget" in _dims(items)


def test_search_term_high_click_no_order(db):
    db.add(FactSearchTerm(shop_id=1, date=D1, search_term="stbad",
                          clicks=10, orders=0, spend=20.0, sales=0.0))
    db.commit()
    items = run_rules(db, 1, D1, D2, 35.0)
    assert "negative" in _dims(items)


def test_search_term_gold(db):
    db.add(FactSearchTerm(shop_id=1, date=D1, search_term="stgood",
                          clicks=10, orders=2, spend=40.0, sales=200.0))
    db.commit()
    items = run_rules(db, 1, D1, D2, 35.0)
    assert "keyword_add" in _dims(items)


def test_listing_low_ctr_low_cvr(db):
    _add(db, impressions=20000, clicks=20, orders=1, sales=200.0, spend=50.0)
    db.commit()
    items = run_rules(db, 1, D1, D2, 35.0)
    assert "listing" in _dims(items)


def test_inventory_critical(db):
    db.add(FactInventory(shop_id=1, date=D1, asin="B0LOW", sku="S1",
                         qty=3, inbound=0, days_of_cover=2))
    db.add(FactListingDaily(shop_id=1, date=D1, asin="B0LOW", units=2))
    db.commit()
    items = run_rules(db, 1, D1, D2, 35.0)
    assert "inventory" in _dims(items)


def test_inventory_fallback(db):
    # 仅业务报告库存总量（无 fact_inventory）：日均销量高、库存低 → 可售天数 < 阈值
    db.add(FactListingDaily(shop_id=1, date=D1, asin="B0X", inventory=2, units=10))
    db.commit()
    items = run_rules(db, 1, D1, D2, 35.0)
    assert "inventory" in _dims(items)


def test_structure_concentration(db):
    _add(db, campaign_id="BIG", campaign_name="BIG", spend=400.0, sales=400.0,
         clicks=50, impressions=5000, orders=10)
    _add(db, campaign_id="SMALL", campaign_name="SMALL", spend=50.0, sales=200.0,
         clicks=10, impressions=1000, orders=5)
    db.commit()
    items = run_rules(db, 1, D1, D2, 35.0)
    assert "structure" in _dims(items)


def test_aba_gap(db):
    db.add(FactAba(shop_id=1, week_start=D1, search_term="brandnewtermzzz",
                   search_rank=50))
    db.commit()
    items = run_rules(db, 1, D1, D2, 35.0)
    assert "keyword_add" in _dims(items)


def test_placement(db):
    _add(db)
    db.commit()
    items = run_rules(db, 1, D1, D2, 35.0)
    assert "placement" in _dims(items)


def test_weekday_schedule(db):
    for i in range(12):
        _add(db, date=D1 + timedelta(days=i), campaign_id="C1", campaign_name="C1",
             spend=10.0, sales=50.0, clicks=5, impressions=500, orders=1)
    db.commit()
    items = run_rules(db, 1, D1, D2, 35.0)
    assert "schedule" in _dims(items)


def test_risk_zero_sales(db):
    _add(db, spend=100.0, sales=0.0, orders=0, clicks=10, impressions=1000)
    db.commit()
    items = run_rules(db, 1, D1, D2, 35.0)
    assert "risk" in _dims(items)


def test_shared_seed_blocks(db):
    # 仅依赖种子数据触发：竞品库（块11）、排名掉落（块14）、复盘（块12）
    items = run_rules(db, 1, D1, D2, 35.0)
    dims = _dims(items)
    assert "review" in dims
    assert "competitor" in dims
