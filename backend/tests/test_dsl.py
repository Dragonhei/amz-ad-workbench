"""DSL 解析/校验/求值单测。"""
from datetime import date

from app.dsl import parse_dsl, validate_rule, check_dsl, dsl_meta, evaluate_rule
from app.models import FactAdPerf


def _insert(facts, **kw):
    base = dict(shop_id=1, date=date(2026, 1, 15), ad_format="SP", level="campaign",
                campaign_id="C1", campaign_name="Campaign A", impressions=1000, clicks=20,
                spend=200.0, orders=5, units=5, sales=500.0)
    base.update(kw)
    facts.add(FactAdPerf(**base))
    facts.commit()


# —— 解析 ——
def test_parse_dsl_valid():
    d = parse_dsl('WHEN acos > 40 FOR campaign THEN SUGGEST bid "活动「{scope}」ACOS 达 {value}%" WITH SEVERITY mid')
    assert d["valid"]
    assert d["metric"] == "acos"
    assert d["op"] == ">"
    assert d["threshold"] == 40
    assert d["scope"] == "campaign"
    assert d["dimension"] == "bid"
    assert d["severity"] == "mid"


def test_parse_dsl_invalid_syntax():
    d = parse_dsl("随便写点东西")
    assert not d["valid"]
    assert d["error"]


def test_parse_dsl_invalid_threshold():
    d = parse_dsl('WHEN acos > abc THEN bid "x"')
    assert not d["valid"]


def test_parse_dsl_defaults():
    d = parse_dsl('WHEN ctr < 0.2 THEN listing "关键词 CTR 低"')
    assert d["valid"]
    assert d["scope"] == "account"
    assert d["severity"] == "mid"
    assert d["dimension"] == "listing"


# —— 校验 ——
def test_validate_rule_ok():
    good = parse_dsl('WHEN acos > 40 FOR campaign THEN bid "x"')
    assert validate_rule(good) == []


def test_validate_rule_unknown_metric():
    bad = parse_dsl('WHEN nope > 1 THEN bid "x"')
    assert any("未知指标" in e for e in validate_rule(bad))


def test_validate_rule_unknown_dimension():
    bad = parse_dsl('WHEN acos > 1 THEN unknown_dim "x"')
    assert any("未知维度" in e for e in validate_rule(bad))


def test_check_dsl_entrypoint():
    assert check_dsl('WHEN acos > 40 FOR campaign THEN bid "x"')["ok"]
    r = check_dsl("garbage")
    assert not r["ok"] and r["errors"]


# —— 元数据 ——
def test_dsl_meta():
    m = dsl_meta()
    for k in ("metrics", "ops", "scopes", "dimensions", "severities"):
        assert m[k], k
    assert any(x["code"] == "acos" for x in m["metrics"])
    assert any(x["code"] == "campaign" for x in m["scopes"])


# —— 求值（数据驱动）——
def test_evaluate_rule_triggers(facts):
    _insert(facts)  # spend 200 / sales 500 -> ACOS 40%
    d = parse_dsl('WHEN acos > 30 FOR account THEN bid "账户 ACOS 偏高"')
    items = evaluate_rule(facts, 1, date(2026, 1, 1), date(2026, 1, 31), d)
    assert isinstance(items, list) and len(items) >= 1
    it = items[0]
    for k in ("dimension", "title", "detail", "action", "priority", "confidence", "evidence"):
        assert k in it
    assert it["priority"] in ("P0", "P1", "P2")


def test_evaluate_rule_no_trigger(facts):
    _insert(facts, spend=10.0, sales=1000.0)  # ACOS 1%
    d = parse_dsl('WHEN acos > 50 FOR account THEN bid "x"')
    assert evaluate_rule(facts, 1, date(2026, 1, 1), date(2026, 1, 31), d) == []


def test_evaluate_rule_invalid_short_circuits():
    assert evaluate_rule(None, 1, None, None, {"valid": False}) == []


def test_validate_rule_unknown_severity():
    bad = parse_dsl('WHEN acos > 1 THEN bid "x" WITH SEVERITY weird')
    assert any("未知严重度" in e for e in validate_rule(bad))


def test_evaluate_rule_campaign_scope_triggers(facts):
    _insert(facts, campaign_id="HOT", campaign_name="Hot", spend=300.0, sales=500.0)  # ACOS 60%
    d = parse_dsl('WHEN acos > 30 FOR campaign THEN bid "下调高 ACOS 活动竞价"')
    items = evaluate_rule(facts, 1, date(2026, 1, 1), date(2026, 1, 31), d)
    assert any("Hot" in it["detail"] for it in items)


def test_evaluate_rule_operator_lt_no_trigger(facts):
    _insert(facts)  # ACOS 40%
    d = parse_dsl('WHEN acos < 10 FOR account THEN bid "x"')
    assert evaluate_rule(facts, 1, date(2026, 1, 1), date(2026, 1, 31), d) == []
    d2 = parse_dsl('WHEN acos > 10 FOR account THEN bid "x"')
    assert evaluate_rule(facts, 1, date(2026, 1, 1), date(2026, 1, 31), d2)  # 40>10 触发


def test_dsl_meta_ops_have_codes():
    m = dsl_meta()
    assert all("code" in op and "label" in op for op in m["ops"])
    assert any(op["sym"] == ">" for op in m["ops"])


def test_validate_rule_unreachable_branches():
    # 这些分支为防御性代码（parse_dsl 不会产出），用构造 dict 直接触发
    parsed = {"valid": True, "metric": "acos", "op": "**", "scope": "account",
              "dimension": "bid", "severity": "mid", "template": "x"}
    assert any("不支持的运算符" in e for e in validate_rule(parsed))
    parsed2 = dict(parsed, template="")
    assert any("模板不能为空" in e for e in validate_rule(parsed2))


def test_evaluate_rule_keyword_scope(facts):
    _insert(facts, keyword_text="wireless earbuds", campaign_id="K1", spend=300.0, sales=400.0)
    d = parse_dsl('WHEN acos > 30 FOR keyword THEN keyword_add "拓展长尾词"')
    items = evaluate_rule(facts, 1, date(2026, 1, 1), date(2026, 1, 31), d)
    assert any("wireless earbuds" in it["detail"] for it in items)


def test_parse_dsl_none_input():
    d = parse_dsl(None)
    assert not d["valid"]


def test_evaluate_rule_adgroup_scope(facts):
    _insert(facts, adgroup_id="AG1", adgroup_name="AdGroup A", spend=300.0, sales=400.0)
    d = parse_dsl('WHEN acos > 30 FOR adgroup THEN structure "审视广告组结构"')
    items = evaluate_rule(facts, 1, date(2026, 1, 1), date(2026, 1, 31), d)
    assert any("AdGroup A" in it["detail"] for it in items)


def test_evaluate_rule_adformat_scope(facts):
    _insert(facts, ad_format="SB", spend=300.0, sales=400.0)
    d = parse_dsl('WHEN acos > 30 FOR ad_format THEN placement "调整广告格式"')
    items = evaluate_rule(facts, 1, date(2026, 1, 1), date(2026, 1, 31), d)
    assert any("SB" in it["detail"] for it in items)


def test_evaluate_rule_placement_scope(facts):
    _insert(facts, placement="top", spend=300.0, sales=400.0)
    d = parse_dsl('WHEN acos > 30 FOR placement THEN placement "优化投放位置"')
    items = evaluate_rule(facts, 1, date(2026, 1, 1), date(2026, 1, 31), d)
    assert any("top" in it["detail"] for it in items)


def test_evaluate_rule_targeting_scope(facts):
    _insert(facts, targeting="manual", spend=300.0, sales=400.0)
    d = parse_dsl('WHEN acos > 30 FOR targeting THEN keyword_add "调整定向"')
    items = evaluate_rule(facts, 1, date(2026, 1, 1), date(2026, 1, 31), d)
    assert any("manual" in it["detail"] for it in items)


def test_evaluate_rule_multiple_triggered(facts):
    _insert(facts, campaign_id="C1", campaign_name="One", spend=300.0, sales=400.0)
    _insert(facts, campaign_id="C2", campaign_name="Two", spend=400.0, sales=400.0)
    d = parse_dsl('WHEN acos > 30 FOR campaign THEN bid "下调竞价"')
    items = evaluate_rule(facts, 1, date(2026, 1, 1), date(2026, 1, 31), d)
    assert len(items) == 1
    assert "One" in items[0]["detail"] and "Two" in items[0]["detail"]

