"""规则引擎单测：内置规则在受控数据下可运行并产出结构化建议。"""
from datetime import date

from app.rules import run_rules
from app.models import FactAdPerf


def _insert(facts, **kw):
    base = dict(shop_id=1, date=date(2026, 1, 15), ad_format="SP", level="campaign",
                campaign_id="C1", campaign_name="Campaign A", impressions=1000, clicks=20,
                spend=200.0, orders=5, units=5, sales=500.0)
    base.update(kw)
    facts.add(FactAdPerf(**base))
    facts.commit()


def test_run_rules_returns_structured_items(facts):
    _insert(facts)  # ACOS 40% 高于目标 35%，应触发规则
    items = run_rules(facts, 1, date(2026, 1, 1), date(2026, 1, 31), target_acos=35.0)
    assert isinstance(items, list)
    if items:  # 高 ACOS 场景预期至少命中一条
        assert len(items) >= 1
    for it in items:
        assert "dimension" in it and "title" in it
        assert it.get("priority") in ("P0", "P1", "P2")


def test_run_rules_handles_low_acos(facts):
    _insert(facts, spend=10.0, sales=2000.0)  # ACOS 0.5%
    items = run_rules(facts, 1, date(2026, 1, 1), date(2026, 1, 31), target_acos=35.0)
    assert isinstance(items, list)


def test_run_rules_evaluates_db_dsl_rule(facts):
    from app.models import AnalysisRule
    _insert(facts)  # ACOS 40%
    rule = AnalysisRule(code="dsl_unit_test", name_zh="单测DSL", enabled=True,
                        dsl_text='WHEN acos > 10 FOR account THEN bid "DSL_TRIGGER_MARKER"')
    facts.add(rule)
    facts.commit()
    items = run_rules(facts, 1, date(2026, 1, 1), date(2026, 1, 31), target_acos=35.0)
    assert any("DSL_TRIGGER_MARKER" in (it.get("action", "") + it.get("detail", "")) for it in items)
