"""LLM 分析：模型配置、规则与提示词、运行生成 12 维方案、证据绑定与用量记录。"""
import hashlib
import json
import time
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth import assert_shop_access, current_user
from ..db import get_db
from ..llm import call_llm, decrypt_key, encrypt_key, mask_key, normalize_items
from ..metrics import METRICS, aggregate, period_totals
from ..models import (ActionExecution, ActionItem, AnalysisRun, Evidence, FactAba,
                      FactSearchTerm, KbBidRule, KbKeyword, LlmProvider, PromptTemplate,
                      Shop, UsageLog, User, AnalysisRule, utcnow)
from ..rules import DEFAULT_PROMPT, DEFAULT_RULES, DIMENSIONS, run_rules
from ..dsl import dsl_meta, check_dsl

router = APIRouter(prefix="/api/analysis", tags=["analysis"])
PRICE_IN = 0.15 / 1_000_000
PRICE_OUT = 0.6 / 1_000_000


# ---------------------------------------------------------------- Provider
@router.get("/providers")
def list_providers(db: Session = Depends(get_db), u: User = Depends(current_user)):
    rows = db.query(LlmProvider).all()
    return {"items": [{"id": r.id, "name": r.name, "endpoint": r.endpoint, "model": r.model,
                       "api_key_mask": mask_key(r.api_key_enc), "has_key": bool(r.api_key_enc),
                       "params": json.loads(r.params_json or "{}"), "enabled": r.enabled,
                       "is_default": r.is_default} for r in rows]}


class ProviderIn(BaseModel):
    id: Optional[int] = None
    name: str = "default"
    endpoint: str = ""
    model: str = ""
    api_key: str = ""
    params: dict = {}
    enabled: bool = False
    is_default: bool = False


@router.post("/providers")
def save_provider(p: ProviderIn, db: Session = Depends(get_db), u: User = Depends(current_user)):
    obj = db.query(LlmProvider).get(p.id) if p.id else LlmProvider()
    if not obj:
        raise HTTPException(404, "配置不存在")
    obj.name = p.name
    if p.endpoint:
        obj.endpoint = p.endpoint
    if p.model:
        obj.model = p.model
    if p.api_key:
        obj.api_key_enc = encrypt_key(p.api_key)
    obj.params_json = json.dumps(p.params or {}, ensure_ascii=False)
    obj.enabled = p.enabled
    obj.is_default = p.is_default
    if p.is_default:
        for other in db.query(LlmProvider).filter(LlmProvider.id != obj.id).all():
            other.is_default = False
    db.add(obj)
    db.commit()
    return {"ok": True, "id": obj.id, "api_key_mask": mask_key(obj.api_key_enc)}


@router.delete("/providers/{pid}")
def del_provider(pid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    obj = db.query(LlmProvider).get(pid)
    if obj:
        db.delete(obj)
        db.commit()
    return {"ok": True}


@router.post("/providers/{pid}/test")
def test_provider(pid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    p = db.query(LlmProvider).get(pid)
    if not p:
        raise HTTPException(404, "配置不存在")
    data, usage, err = call_llm(p, "你是一个JSON输出助手", '输出：{"items":[]}')
    if err:
        raise HTTPException(400, err["message"])
    return {"ok": True, "usage": usage}


# ---------------------------------------------------------------- 规则与提示词
@router.get("/rules")
def list_rules(db: Session = Depends(get_db), u: User = Depends(current_user)):
    rows = db.query(AnalysisRule).all()
    return {"items": [{"id": r.id, "code": r.code, "name_zh": r.name_zh, "dimension": r.dimension,
                       "condition": json.loads(r.condition_json or "{}"), "priority": r.priority,
                       "enabled": r.enabled, "advice_template": r.advice_template,
                       "dsl_text": r.dsl_text or ""} for r in rows]}


class RuleIn(BaseModel):
    id: int
    enabled: Optional[bool] = None
    condition: Optional[dict] = None
    priority: Optional[int] = None
    advice_template: Optional[str] = None
    dsl_text: Optional[str] = None


@router.put("/rules/{rid}")
def update_rule(rid: int, body: RuleIn, db: Session = Depends(get_db), u: User = Depends(current_user)):
    r = db.query(AnalysisRule).get(rid)
    if not r:
        raise HTTPException(404, "规则不存在")
    if body.enabled is not None:
        r.enabled = body.enabled
    if body.condition is not None:
        r.condition_json = json.dumps(body.condition, ensure_ascii=False)
    if body.priority is not None:
        r.priority = body.priority
    if body.advice_template is not None:
        r.advice_template = body.advice_template
    if body.dsl_text is not None:
        r.dsl_text = body.dsl_text
    db.commit()
    return {"ok": True}


class RuleCreateIn(BaseModel):
    code: str
    name_zh: str
    dimension: str
    dsl_text: str = ""
    priority: int = 5
    enabled: bool = True
    advice_template: str = ""


@router.post("/rules")
def create_rule(body: RuleCreateIn, db: Session = Depends(get_db), u: User = Depends(current_user)):
    if db.query(AnalysisRule).filter(AnalysisRule.code == body.code).first():
        raise HTTPException(400, f"规则代码 {body.code} 已存在")
    r = AnalysisRule(code=body.code, name_zh=body.name_zh, dimension=body.dimension,
                     dsl_text=body.dsl_text, priority=body.priority, enabled=body.enabled,
                     advice_template=body.advice_template, condition_json="{}")
    db.add(r)
    db.commit()
    return {"ok": True, "id": r.id}


@router.delete("/rules/{rid}")
def delete_rule(rid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    r = db.query(AnalysisRule).get(rid)
    if not r:
        raise HTTPException(404, "规则不存在")
    db.delete(r)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- DSL 可视化规则
@router.get("/dsl/meta")
def dsl_rule_meta():
    return dsl_meta()


@router.get("/dsl/validate")
def dsl_validate(text: str = "", db: Session = Depends(get_db), u: User = Depends(current_user)):
    res = check_dsl(text)
    return {"ok": res["ok"], "errors": res["errors"], "parsed": res["parsed"]}


@router.get("/dimensions")
def dimensions():
    return {"items": DIMENSIONS}


@router.get("/prompt")
def get_prompt(code: str = "default", db: Session = Depends(get_db), u: User = Depends(current_user)):
    t = db.query(PromptTemplate).filter(PromptTemplate.code == code).first()
    return {"code": code, "content": t.content if t else DEFAULT_PROMPT}


class PromptIn(BaseModel):
    code: str = "default"
    content: str = ""


@router.put("/prompt")
def save_prompt(p: PromptIn, db: Session = Depends(get_db), u: User = Depends(current_user)):
    t = db.query(PromptTemplate).filter(PromptTemplate.code == p.code).first()
    if not t:
        t = PromptTemplate(code=p.code, name_zh="12 维分析提示词")
    t.content = p.content
    db.add(t)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- 运行分析
class RunIn(BaseModel):
    shop_id: int = 1
    start: str = ""
    end: str = ""
    target_acos: float = 35.0
    provider_id: Optional[int] = None
    use_llm: bool = True
    notify: bool = False          # P2-3：运行完成后把 P0/P1 告警推送到启用的渠道


def _build_context(db, shop_id, d1, d2, target_acos):
    camp = aggregate(db, shop_id, d1, d2, group_by="campaign", sort_by="spend")
    kw = aggregate(db, shop_id, d1, d2, group_by="keyword", sort_by="spend",
                   filters={"min_clicks": 3})
    s = camp["summary"]
    summary_text = (f"曝光 {s['impressions']}｜点击 {s['clicks']}｜CTR {s['ctr']}%｜"
                    f"CPC ${s['cpc']}｜花费 ${s['spend']}｜订单 {s['orders']}｜CVR {s['cvr']}%｜"
                    f"广告销售额 ${s['sales']}｜ACOS {s['acos']}%｜ROAS {s['roas']}｜"
                    f"TACOS {s['tacos']}%｜总销售额 ${round(period_totals(db, shop_id, d1, d2), 2)}")
    top_rows = "\n".join(f"{i+1}. {r.get('campaign_name')}：花费 ${r['spend']}、销售 ${r['sales']}、"
                         f"ACOS {r['acos']}%、订单 {r['orders']}、CTR {r['ctr']}%"
                         for i, r in enumerate(camp["rows"][:12]))
    top_kw = "\n".join(f"{i+1}. {r.get('keyword_text') or '(空)'}（{r.get('match_type') or '-'}）："
                       f"点击 {r['clicks']}、花费 ${r['spend']}、订单 {r['orders']}、ACOS {r['acos']}%"
                       for i, r in enumerate(kw["rows"][:15]))
    st = (db.query(FactSearchTerm.search_term, func.sum(FactSearchTerm.clicks).label("clicks"),
                   func.sum(FactSearchTerm.spend).label("spend"),
                   func.sum(FactSearchTerm.orders).label("orders"),
                   func.sum(FactSearchTerm.sales).label("sales"))
          .filter(FactSearchTerm.shop_id == shop_id, FactSearchTerm.date >= d1,
                  FactSearchTerm.date <= d2)
          .group_by(FactSearchTerm.search_term).order_by(func.sum(FactSearchTerm.spend).desc())
          .limit(15).all())
    st_text = "\n".join(f"- {r.search_term}：{r.clicks} 点击 / ${round(r.spend or 0, 2)} / "
                        f"{r.orders} 单 / ${round(r.sales or 0, 2)}" for r in st) or "（无搜索词数据）"
    kws = db.query(KbKeyword).filter(KbKeyword.shop_id.in_([shop_id, 0])).limit(30).all()
    kb_text = "、".join(f"{k.term}({k.status})" for k in kws) or "（空）"
    bids = db.query(KbBidRule).filter(KbBidRule.shop_id.in_([shop_id, 0])).limit(20).all()
    bid_text = "；".join(f"{b.keyword}/{b.match_type} 基准${b.base_cpc} 区间[{b.min_cpc},{b.max_cpc}]"
                        for b in bids) or "（空）"
    return {"summary_text": summary_text, "top_rows": top_rows or "（无活动数据）",
            "top_kw": top_kw or "（无关键词数据）", "st_text": st_text,
            "kb_text": kb_text, "bid_text": bid_text, "summary": s}


@router.post("/run")
def run(body: RunIn, db: Session = Depends(get_db), u: User = Depends(current_user)):
    assert_shop_access(u, body.shop_id)
    t0 = time.time()
    from ..metrics import date_range_of as _range
    _d1, _d2 = _range(db, body.shop_id)
    d1 = date.fromisoformat(body.start) if body.start else _d1
    d2 = date.fromisoformat(body.end) if body.end else _d2
    shop = db.query(Shop).get(body.shop_id)
    provider = db.query(LlmProvider).get(body.provider_id) if body.provider_id else \
        db.query(LlmProvider).filter(LlmProvider.is_default.is_(True)).first()

    ctx = _build_context(db, body.shop_id, d1, d2, body.target_acos)
    rule_items = run_rules(db, body.shop_id, d1, d2, body.target_acos)
    rule_hits = "\n".join(f"[{i['dimension']}] {i['title']}" for i in rule_items)

    fingerprint = hashlib.md5(
        f"{body.shop_id}|{d1}|{d2}|{body.target_acos}|{ctx['summary_text']}".encode()).hexdigest()
    cached = db.query(AnalysisRun).filter(AnalysisRun.fingerprint == fingerprint,
                                          AnalysisRun.status == "success",
                                          AnalysisRun.mode == "llm").first()
    if cached and body.use_llm:
        return {"run_id": cached.id, "mode": "llm", "cached": True, "message": "命中缓存，直接返回上次结果",
                "items": _items_of(db, cached.id)}

    mode, err_msg, usage = "rule", "", {}
    items = rule_items
    if body.use_llm and provider and provider.enabled:
        tmpl = db.query(PromptTemplate).filter(PromptTemplate.code == "default").first()
        content = (tmpl.content if tmpl else DEFAULT_PROMPT)
        prompt = content.format(
            shop_name=shop.name if shop else f"店铺{body.shop_id}", date_start=d1, date_end=d2,
            target_acos=body.target_acos, marketplace=(shop.marketplace if shop else "US"),
            summary_text=ctx["summary_text"], top_rows=ctx["top_rows"] + "\n\n关键词维度：\n" + ctx["top_kw"],
            search_terms=ctx["st_text"], rule_hits=rule_hits or "（无）",
            kb_keywords=ctx["kb_text"], kb_bids=ctx["bid_text"])
        data, usage, err = call_llm(provider, "你是资深亚马逊广告投放专家，只输出严格 JSON。", prompt)
        if data:
            norm = normalize_items(data)
            if norm:
                items = norm
                mode = "llm"
            else:
                err_msg = "模型输出未能归入 12 维，已降级为内置规则引擎结果"
        elif err:
            err_msg = err["message"] + "，已降级为内置规则引擎结果"

    pt = int(usage.get("prompt_tokens") or len(prompt) / 4 if mode == "llm" else 0)
    ct = int(usage.get("completion_tokens") or 0)
    cost = round(pt * PRICE_IN + ct * PRICE_OUT, 6)
    run_obj = AnalysisRun(shop_id=body.shop_id, user_id=u.id, date_start=d1, date_end=d2,
                          scope_json=json.dumps({"target_acos": body.target_acos}),
                          provider_id=provider.id if provider else None, mode=mode,
                          status="success", tokens=pt + ct, cost=cost,
                          duration_ms=int((time.time() - t0) * 1000),
                          message=err_msg, fingerprint=fingerprint)
    db.add(run_obj)
    db.flush()

    item_objs = []
    for it in items:
        item = ActionItem(run_id=run_obj.id, dimension=it["dimension"], title=it["title"],
                          detail=it.get("detail", ""), action=it.get("action", ""),
                          expected_impact=it.get("expected_impact", ""),
                          priority=it.get("priority", "P2"),
                          confidence=float(it.get("confidence", 0.6)))
        db.add(item)
        db.flush()
        item_objs.append(item)
        evs = it.get("evidence") or []
        if isinstance(evs, dict):
            evs = [evs]
        for e in evs:
            if isinstance(e, dict):
                db.add(Evidence(item_id=item.id, metric_path=str(e.get("metric_path", ""))[:250],
                                snapshot_json=json.dumps(e.get("snapshot", e), ensure_ascii=False)[:4000]))
    db.add(UsageLog(user_id=u.id, shop_id=body.shop_id, run_type="analysis",
                    provider=(provider.name if provider else "rule-engine"),
                    model=(provider.model if provider else "builtin-rules"),
                    prompt_tokens=pt, completion_tokens=ct, cost=cost,
                    status="success" if not err_msg else "degraded", message=err_msg))
    db.commit()

    # P2-3：运行完成后把 P0/P1 级告警推送到启用的通知渠道
    notify_sent = 0
    if body.notify:
        from ..routers.notify import dispatch_alerts
        recs = dispatch_alerts(db, run_obj.id, item_objs, body.shop_id)
        notify_sent = len(recs)

    return {"run_id": run_obj.id, "mode": mode, "cached": False,
            "message": err_msg or ("大模型分析完成" if mode == "llm" else "使用内置规则引擎（未启用模型或调用失败）"),
            "tokens": pt + ct, "cost": cost, "notify_sent": notify_sent,
            "items": _items_of(db, run_obj.id)}


def _items_of(db, run_id):
    items = db.query(ActionItem).filter(ActionItem.run_id == run_id).all()
    out = []
    for it in items:
        evs = db.query(Evidence).filter(Evidence.item_id == it.id).all()
        out.append({"id": it.id, "dimension": it.dimension, "title": it.title, "detail": it.detail,
                    "action": it.action, "expected_impact": it.expected_impact,
                    "priority": it.priority, "confidence": it.confidence, "status": it.status,
                    "executed": bool(it.executed),
                    "evidence": [{"metric_path": e.metric_path, "snapshot": e.snapshot_json} for e in evs]})
    return out


@router.get("/runs")
def runs(shop_id: int = 1, limit: int = 20, db: Session = Depends(get_db), u: User = Depends(current_user)):
    rows = (db.query(AnalysisRun).filter(AnalysisRun.shop_id == shop_id)
            .order_by(AnalysisRun.id.desc()).limit(limit).all())
    return {"items": [{"id": r.id, "mode": r.mode, "date_start": str(r.date_start),
                       "date_end": str(r.date_end), "tokens": r.tokens, "cost": r.cost,
                       "duration_ms": r.duration_ms, "message": r.message,
                       "created_at": r.created_at.strftime("%Y-%m-%d %H:%M")} for r in rows]}


@router.get("/runs/{rid}")
def run_detail(rid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    r = db.query(AnalysisRun).get(rid)
    if not r:
        raise HTTPException(404, "运行记录不存在")
    return {"run": {"id": r.id, "mode": r.mode, "date_start": str(r.date_start),
                    "date_end": str(r.date_end), "tokens": r.tokens, "cost": r.cost,
                    "message": r.message}, "items": _items_of(db, rid)}


class StatusIn(BaseModel):
    status: str


@router.post("/items/{iid}/status")
def item_status(iid: int, body: StatusIn, db: Session = Depends(get_db), u: User = Depends(current_user)):
    it = db.query(ActionItem).get(iid)
    if not it:
        raise HTTPException(404, "建议不存在")
    it.status = body.status
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- P1-5 执行回填与效果复盘
RETRO_METRICS = ["acos", "tacos", "cvr", "ctr", "cpc", "spend", "sales", "orders", "roas",
                 "impressions", "clicks"]


def _snapshot(db, shop_id, d1, d2):
    """取某店铺在 [d1,d2] 的整体聚合摘要，作为执行前后指标快照。"""
    try:
        return aggregate(db, shop_id, d1, d2, group_by="campaign")["summary"]
    except Exception:
        return {}


def _calc_lift(before, after):
    """计算前后快照各核心指标的环比与改善方向。"""
    hb = {m["code"]: m["higher_better"] for m in METRICS}
    lift = {}
    for code in RETRO_METRICS:
        b, a = before.get(code), after.get(code)
        if b is None or a is None:
            lift[code] = None
            continue
        delta_pct = ((a - b) / b * 100) if b else None
        improved = False
        if delta_pct is not None:
            improved = (a > b) if hb.get(code, True) else (a < b)
        lift[code] = {"before": b, "after": a,
                      "delta_pct": round(delta_pct, 2) if delta_pct is not None else None,
                      "improved": improved}
    return lift


class ExecuteIn(BaseModel):
    change_note: str = ""
    before_days: int = 7
    after_days: int = 7
    exec_date: str = ""          # YYYY-MM-DD；默认今天


@router.post("/items/{iid}/execute")
def execute_item(iid: int, body: ExecuteIn, db: Session = Depends(get_db), u: User = Depends(current_user)):
    it = db.query(ActionItem).get(iid)
    if not it:
        raise HTTPException(404, "建议不存在")
    run = db.query(AnalysisRun).get(it.run_id) if it.run_id else None
    shop_id = (run.shop_id if run else 1)
    exec_date = date.fromisoformat(body.exec_date) if body.exec_date else date.today()
    before_start = exec_date - timedelta(days=body.before_days)
    before_end = exec_date - timedelta(days=1)
    after_start = exec_date
    after_end = exec_date + timedelta(days=max(body.after_days - 1, 0))
    before = _snapshot(db, shop_id, before_start, before_end)
    after = _snapshot(db, shop_id, after_start, after_end)
    ex = db.query(ActionExecution).filter(ActionExecution.action_id == iid).first()
    if not ex:
        ex = ActionExecution(action_id=iid, shop_id=shop_id)
        db.add(ex)
    ex.shop_id = shop_id
    ex.executed_at = utcnow()
    ex.exec_date = exec_date
    ex.before_days = body.before_days
    ex.after_days = body.after_days
    ex.change_note = body.change_note
    ex.before_snapshot = json.dumps(before, ensure_ascii=False)
    ex.after_snapshot = json.dumps(after, ensure_ascii=False)
    it.executed = True
    it.executed_at = utcnow()
    db.commit()
    return {"ok": True, "execution_id": ex.id,
            "before": before, "after": after,
            "lift": _calc_lift(before, after)}


@router.get("/items/{iid}/execution")
def get_execution(iid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    ex = db.query(ActionExecution).filter(ActionExecution.action_id == iid).first()
    if not ex:
        return {"ok": False, "execution": None}
    it = db.query(ActionItem).get(ex.action_id)
    return {"ok": True, "execution": {
        "id": ex.id, "action_id": ex.action_id,
        "title": it.title if it else "", "dimension": it.dimension if it else "",
        "exec_date": str(ex.exec_date), "before_days": ex.before_days,
        "after_days": ex.after_days, "change_note": ex.change_note,
        "before": json.loads(ex.before_snapshot or "{}"),
        "after": json.loads(ex.after_snapshot or "{}"),
        "lift": _calc_lift(json.loads(ex.before_snapshot or "{}"),
                           json.loads(ex.after_snapshot or "{}")),
        "executed_at": ex.executed_at.strftime("%Y-%m-%d %H:%M") if ex.executed_at else "",
    }}


@router.get("/retro")
def retro(shop_id: int = 1, recompute: int = 0, db: Session = Depends(get_db), u: User = Depends(current_user)):
    exs = (db.query(ActionExecution).filter(ActionExecution.shop_id == shop_id)
           .order_by(ActionExecution.exec_date.desc()).all())
    out = []
    for ex in exs:
        before = json.loads(ex.before_snapshot or "{}")
        after = json.loads(ex.after_snapshot or "{}")
        if recompute:
            try:
                before = _snapshot(db, ex.shop_id, ex.exec_date - timedelta(days=ex.before_days),
                                   ex.exec_date - timedelta(days=1))
                after = _snapshot(db, ex.shop_id, ex.exec_date,
                                  ex.exec_date + timedelta(days=max(ex.after_days - 1, 0)))
            except Exception:
                pass
        it = db.query(ActionItem).get(ex.action_id)
        out.append({
            "id": ex.id, "action_id": ex.action_id,
            "title": it.title if it else "", "dimension": it.dimension if it else "",
            "priority": it.priority if it else "",
            "exec_date": str(ex.exec_date), "before_days": ex.before_days,
            "after_days": ex.after_days, "change_note": ex.change_note,
            "before": before, "after": after, "lift": _calc_lift(before, after),
            "executed_at": ex.executed_at.strftime("%Y-%m-%d %H:%M") if ex.executed_at else "",
        })
    return {"items": out}
