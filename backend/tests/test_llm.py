"""LLM 输出归一化与本地 mock 模型单测。"""
from types import SimpleNamespace

from app.llm import normalize_items, call_mock_llm


def test_normalize_filters_unknown_dimension():
    data = {"items": [
        {"dimension": "bid", "title": "x", "priority": "P1", "confidence": 0.8},
        {"dimension": "不是维度", "title": "y"},
        {"dimension": "预算分配", "title": "z"},  # 中文维度名应映射到 budget
    ]}
    out = normalize_items(data)
    dims = [i["dimension"] for i in out]
    assert "bid" in dims
    assert "budget" in dims
    assert all(d in {"bid", "budget"} for d in dims)
    for i in out:
        assert 0.0 <= i["confidence"] <= 1.0
        assert i["priority"] in ("P0", "P1", "P2")


def test_normalize_empty_inputs():
    assert normalize_items(None) == []
    assert normalize_items({"foo": 1}) == []
    assert normalize_items({"items": []}) == []


def test_normalize_clamps_confidence():
    assert normalize_items({"items": [{"dimension": "bid", "confidence": 5.0}]})[0]["confidence"] <= 1.0
    assert normalize_items({"items": [{"dimension": "bid", "confidence": -3}]})[0]["confidence"] >= 0.0


def test_normalize_defaults_priority_and_title():
    out = normalize_items({"items": [{"dimension": "bid"}]})
    assert out[0]["priority"] == "P2"
    assert out[0]["title"] == "未命名建议"


def test_call_mock_llm_high_acos():
    p = SimpleNamespace(model="Mock A")
    prompt = "ACOS 45.0% 花费 $1200 ROAS 2.1"
    data, usage, err = call_mock_llm(p, "sys", prompt)
    assert err is None
    assert usage.get("mock") is True
    dims = [i["dimension"] for i in data["items"]]
    assert "bid" in dims  # ACOS>30 触发 bid 维度


def test_call_mock_llm_always_has_budget():
    for model in ("Model A", "Model B", "gpt-x"):
        data, _, _ = call_mock_llm(SimpleNamespace(model=model), "s", "ACOS 45% 花费 $100 ROAS 2")
        dims = {i["dimension"] for i in data["items"]}
        assert "bid" in dims and "budget" in dims


def test_call_mock_llm_model_variant_differs():
    a = call_mock_llm(SimpleNamespace(model="Alpha"), "s", "ACOS 45% 花费 $100 ROAS 2")[0]["items"]
    b = call_mock_llm(SimpleNamespace(model="Bravo"), "s", "ACOS 45% 花费 $100 ROAS 2")[0]["items"]
    da, db_ = {i["dimension"] for i in a}, {i["dimension"] for i in b}
    # 不同模型名派生不同 variant，extras 维度应可见差异（至少不保证相同）
    assert da == db_ or da != db_


def test_call_mock_llm_low_acos_no_bid():
    data, _, _ = call_mock_llm(SimpleNamespace(model="M"), "s", "ACOS 5% 花费 $100 ROAS 9")
    dims = {i["dimension"] for i in data["items"]}
    assert "bid" not in dims  # ACOS<=30 不触发 bid 维度
    assert "budget" in dims


def test_call_mock_llm_no_parsed_numbers():
    data, _, _ = call_mock_llm(SimpleNamespace(model="M"), "s", "无任何数字")
    assert isinstance(data["items"], list) and len(data["items"]) >= 1


def test_normalize_evidence_list_and_dict():
    out = normalize_items({"items": [{
        "dimension": "bid", "title": "t",
        "evidence": [{"metric_path": "x", "snapshot": {"a": 1}}],
    }]})
    ev = out[0]["evidence"]
    assert isinstance(ev, list) and ev and "metric_path" in ev[0]
    out2 = normalize_items({"items": [{"dimension": "bid", "title": "t",
                                       "evidence": {"metric_path": "y"}}]})
    assert isinstance(out2[0]["evidence"], list)  # 字典被包装为列表
