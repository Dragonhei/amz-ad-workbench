"""指标聚合单测。"""
from datetime import date

from app.metrics import aggregate
from app.models import FactAdPerf


def _insert(facts, **kw):
    base = dict(shop_id=1, date=date(2026, 1, 15), ad_format="SP", level="campaign",
                campaign_id="C1", campaign_name="Campaign A", impressions=1000, clicks=20,
                spend=200.0, orders=5, units=5, sales=500.0)
    base.update(kw)
    facts.add(FactAdPerf(**base))
    facts.commit()


def test_aggregate_campaign_and_acos(facts):
    _insert(facts)
    res = aggregate(facts, [1], date(2026, 1, 1), date(2026, 1, 31), group_by="campaign")
    assert res["total"] >= 1
    row = res["rows"][0]
    assert row["campaign_id"] == "C1"
    assert 39 < row["acos"] < 41  # 200 / 500 * 100
    assert "summary" in res and "total_sales" in res


def test_aggregate_filter_ad_format(facts):
    _insert(facts, ad_format="SB", campaign_id="SB1")
    _insert(facts, ad_format="SP", campaign_id="SP1")
    sb = aggregate(facts, [1], date(2026, 1, 1), date(2026, 1, 31),
                   group_by="campaign", filters={"ad_format": "SB"})
    assert sb["total"] == 1 and sb["rows"][0]["campaign_id"] == "SB1"
    sp = aggregate(facts, [1], date(2026, 1, 1), date(2026, 1, 31),
                   group_by="campaign", filters={"ad_format": "SP"})
    assert sp["total"] == 1 and sp["rows"][0]["campaign_id"] == "SP1"
    none = aggregate(facts, [1], date(2026, 1, 1), date(2026, 1, 31),
                     group_by="campaign", filters={"ad_format": "SD"})
    assert none["total"] == 0


def test_aggregate_sort_and_min_filters(facts):
    _insert(facts, campaign_id="A", spend=50.0)
    _insert(facts, campaign_id="B", spend=500.0)
    res = aggregate(facts, [1], date(2026, 1, 1), date(2026, 1, 31),
                    group_by="campaign", sort_by="spend", sort_dir="desc")
    assert res["rows"][0]["campaign_id"] == "B"
    min_f = aggregate(facts, [1], date(2026, 1, 1), date(2026, 1, 31),
                      group_by="campaign", filters={"min_spend": 100})
    assert all(r["spend"] >= 100 for r in min_f["rows"])


def test_aggregate_placement_targeting_keyword_filters(facts):
    _insert(facts, campaign_id="P", placement="Top of Search", keyword_text="blue widget", targeting="widget")
    _insert(facts, campaign_id="Q", placement="Product Pages", keyword_text="red widget", targeting="widget")
    pl = aggregate(facts, [1], date(2026, 1, 1), date(2026, 1, 31),
                   group_by="campaign", filters={"placement": "Top of Search"})
    assert pl["total"] == 1 and pl["rows"][0]["campaign_id"] == "P"
    tg = aggregate(facts, [1], date(2026, 1, 1), date(2026, 1, 31),
                   group_by="campaign", filters={"targeting": "widget"})
    assert tg["total"] == 2
    kw = aggregate(facts, [1], date(2026, 1, 1), date(2026, 1, 31),
                   group_by="campaign", filters={"keyword_contains": "blue"})
    assert kw["total"] == 1 and kw["rows"][0]["campaign_id"] == "P"


def test_aggregate_campaign_ids_filter(facts):
    _insert(facts, campaign_id="C1")
    _insert(facts, campaign_id="C9")
    res = aggregate(facts, [1], date(2026, 1, 1), date(2026, 1, 31),
                    group_by="campaign", filters={"campaign_ids": ["C1"]})
    assert res["total"] == 1 and res["rows"][0]["campaign_id"] == "C1"


def test_aggregate_date_range_excludes_out_of_range(facts):
    _insert(facts, date=date(2026, 5, 1))
    res = aggregate(facts, [1], date(2026, 1, 1), date(2026, 1, 31), group_by="campaign")
    assert res["total"] == 0


def test_aggregate_keyword_group(facts):
    _insert(facts, keyword_text="wireless earbuds", campaign_id="C2")
    res = aggregate(facts, [1], date(2026, 1, 1), date(2026, 1, 31), group_by="keyword")
    assert any(r.get("keyword_text") == "wireless earbuds" for r in res["rows"])
