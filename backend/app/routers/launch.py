"""新品冷启动：复用知识库生成广告架构并导出平台可上传表格。"""
import csv
import io
import os
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import current_user
from ..db import BASE_DIR, get_db
from ..models import (FactAba, KbBidRule, KbKeyword, LaunchExport, LaunchPlanNode,
                      LaunchProject, User)

router = APIRouter(prefix="/api/launch", tags=["launch"])
EXPORT_DIR = os.path.join(BASE_DIR, "data", "exports")
os.makedirs(EXPORT_DIR, exist_ok=True)

MATCH_FACTOR = {"exact": 1.1, "phrase": 0.9, "broad": 0.75, "auto": 1.0}


def _bid_for(kw, match, db, shop_id):
    rule = (db.query(KbBidRule)
            .filter(KbBidRule.shop_id.in_([shop_id, 0]), KbBidRule.keyword == kw).first()
            or db.query(KbBidRule)
            .filter(KbBidRule.shop_id.in_([shop_id, 0]), KbBidRule.keyword == "*").first())
    base = rule.base_cpc if rule else 0.8
    lo, hi = (rule.min_cpc, rule.max_cpc) if rule else (0.2, 2.5)
    return round(min(max(round(base * MATCH_FACTOR.get(match, 1.0), 2), lo), hi), 2)


class GenIn(BaseModel):
    shop_id: int = 1
    asin: str
    title: str = ""
    category: str = ""
    target_acos: float = 35.0
    daily_budget: float = 60.0
    cycle_days: int = 30


@router.post("/generate")
def generate(body: GenIn, db: Session = Depends(get_db), u: User = Depends(current_user)):
    if not body.asin:
        raise HTTPException(400, "请填写 ASIN")
    kw_rows = (db.query(KbKeyword)
               .filter(KbKeyword.shop_id.in_([body.shop_id, 0]),
                       KbKeyword.status.in_(["active", "watch"])).all())
    aba_rows = (db.query(FactAba).filter(FactAba.shop_id == body.shop_id)
                .order_by(FactAba.search_rank).limit(30).all())
    have = {k.term.lower() for k in kw_rows}
    pool = []
    for k in kw_rows:
        pool.append({"term": k.term, "source": "知识库", "relevance": k.relevance})
    for a in aba_rows:
        if a.search_term.lower() not in have:
            pool.append({"term": a.search_term, "source": f"ABA#{a.search_rank}", "relevance": "high"})
        if len(pool) >= 60:
            break
    if not pool:
        pool = [{"term": body.title or body.asin, "source": "默认", "relevance": "high"}]

    # 按词长分桶：核心大词 / 属性词 / 长尾词，符合广告投放的实际分组习惯
    def bucket(term):
        n = len(term.split())
        return "核心大词组" if n <= 2 else ("属性词组" if n == 3 else "长尾词组")
    groups = defaultdict(list)
    for p in pool:
        groups[bucket(p["term"])].append(p)
    order = {"核心大词组": 0, "属性词组": 1, "长尾词组": 2}
    top_groups = sorted(groups.items(), key=lambda kv: order.get(kv[0], 9))

    proj = LaunchProject(shop_id=body.shop_id, asin=body.asin, title=body.title,
                         category=body.category, target_acos=body.target_acos,
                         daily_budget=body.daily_budget, cycle_days=body.cycle_days,
                         created_by=u.username)
    db.add(proj)
    db.flush()

    budget = body.daily_budget
    plan = [
        {"name": f"{body.asin} - 自动发现 - Auto", "share": 0.25, "match": "auto",
         "note": "新品期跑词，7 天后提取高转化搜索词转入精准"},
        {"name": f"{body.asin} - 核心精准 - Exact", "share": 0.40, "match": "exact",
         "note": "主推核心词，竞价最高，重点监控 ACOS"},
        {"name": f"{body.asin} - 词组拓展 - Phrase", "share": 0.20, "match": "phrase",
         "note": "承接长尾，出单后转精准"},
        {"name": f"{body.asin} - 商品定位 - SD", "share": 0.15, "match": "asin",
         "note": "投放竞品 ASIN 与互补品类，冷启动期先小规模测试"},
    ]
    for pi, p in enumerate(plan):
        c = LaunchPlanNode(project_id=proj.id, node_type="campaign", name=p["name"],
                           budget=round(budget * p["share"], 2), note=p["note"], sort_order=pi)
        db.add(c)
        db.flush()
        if p["match"] == "asin":
            g = LaunchPlanNode(project_id=proj.id, parent_id=c.id, node_type="adgroup",
                               name="商品定位组", match_type="asin", bid=round(budget * 0.0 + 0.6, 2),
                               note="按竞品 ASIN 与类目投放", sort_order=0)
            db.add(g)
            continue
        if p["match"] == "auto":
            g = LaunchPlanNode(project_id=proj.id, parent_id=c.id, node_type="adgroup",
                               name="自动-紧密匹配", match_type="auto",
                               bid=_bid_for("*", "auto", db, body.shop_id),
                               note="初始竞价取类目基准，7 天调整一次", sort_order=0)
            db.add(g)
            continue
        for gi, (root, items) in enumerate(top_groups):
            g = LaunchPlanNode(project_id=proj.id, parent_id=c.id, node_type="adgroup",
                               name=f"{root} 词组", match_type=p["match"], sort_order=gi)
            db.add(g)
            db.flush()
            for ki, it in enumerate(items[:8]):
                db.add(LaunchPlanNode(project_id=proj.id, parent_id=g.id, node_type="keyword",
                                      name=it["term"], match_type=p["match"],
                                      bid=_bid_for(it["term"], p["match"], db, body.shop_id),
                                      note=f"来源：{it['source']}", sort_order=ki))
    db.commit()
    return {"ok": True, "project_id": proj.id, "asin": body.asin,
            "keyword_pool": len(pool), "budget": budget}


def _tree(db, proj: LaunchProject):
    nodes = (db.query(LaunchPlanNode).filter(LaunchPlanNode.project_id == proj.id)
             .order_by(LaunchPlanNode.sort_order, LaunchPlanNode.id).all())
    by_parent = defaultdict(list)
    for n in nodes:
        by_parent[n.parent_id].append(n)

    def build(pid):
        out = []
        for n in by_parent.get(pid, []):
            out.append({"id": n.id, "node_type": n.node_type, "name": n.name,
                        "match_type": n.match_type, "bid": n.bid, "budget": n.budget,
                        "note": n.note, "children": build(n.id)})
        return out
    return {"project": {"id": proj.id, "asin": proj.asin, "title": proj.title,
                        "category": proj.category, "target_acos": proj.target_acos,
                        "daily_budget": proj.daily_budget, "cycle_days": proj.cycle_days,
                        "status": proj.status,
                        "created_at": proj.created_at.strftime("%Y-%m-%d %H:%M")},
            "tree": build(None)}


@router.get("/projects")
def projects(shop_id: int = 1, db: Session = Depends(get_db), u: User = Depends(current_user)):
    rows = (db.query(LaunchProject).filter(LaunchProject.shop_id == shop_id)
            .order_by(LaunchProject.id.desc()).limit(50).all())
    return {"items": [{"id": r.id, "asin": r.asin, "title": r.title, "target_acos": r.target_acos,
                       "daily_budget": r.daily_budget, "cycle_days": r.cycle_days,
                       "status": r.status, "created_by": r.created_by,
                       "created_at": r.created_at.strftime("%Y-%m-%d %H:%M")} for r in rows]}


@router.get("/projects/{pid}")
def project_detail(pid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    p = db.query(LaunchProject).get(pid)
    if not p:
        raise HTTPException(404, "方案不存在")
    return _tree(db, p)


class NodeIn(BaseModel):
    name: Optional[str] = None
    match_type: Optional[str] = None
    bid: Optional[float] = None
    budget: Optional[float] = None
    note: Optional[str] = None


@router.put("/nodes/{nid}")
def update_node(nid: int, body: NodeIn, db: Session = Depends(get_db), u: User = Depends(current_user)):
    n = db.query(LaunchPlanNode).get(nid)
    if not n:
        raise HTTPException(404, "节点不存在")
    for f in ("name", "match_type", "bid", "budget", "note"):
        v = getattr(body, f)
        if v is not None:
            setattr(n, f, v)
    db.commit()
    return {"ok": True}


@router.post("/nodes")
def add_node(project_id: int, parent_id: int = None, node_type: str = "keyword",
             name: str = "", match_type: str = "exact", bid: float = 0.8,
             db: Session = Depends(get_db), u: User = Depends(current_user)):
    n = LaunchPlanNode(project_id=project_id, parent_id=parent_id, node_type=node_type,
                       name=name, match_type=match_type, bid=bid)
    db.add(n)
    db.commit()
    return {"ok": True, "id": n.id}


@router.delete("/nodes/{nid}")
def del_node(nid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    n = db.query(LaunchPlanNode).get(nid)
    if not n:
        raise HTTPException(404, "节点不存在")
    db.query(LaunchPlanNode).filter(LaunchPlanNode.parent_id == nid).delete()
    db.delete(n)
    db.commit()
    return {"ok": True}


@router.get("/projects/{pid}/export")
def export_bulk(pid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    p = db.query(LaunchProject).get(pid)
    if not p:
        raise HTTPException(404, "方案不存在")
    nodes = (db.query(LaunchPlanNode).filter(LaunchPlanNode.project_id == pid)
             .order_by(LaunchPlanNode.id).all())
    by_id = {n.id: n for n in nodes}
    buf = io.StringIO()
    header = ["Product", "Entity", "Operation", "Campaign Name", "Ad Group Name", "Keyword Text",
              "Match Type", "Bid", "Daily Budget", "State", "Targeting Type", "SKU", "Note"]
    w = csv.writer(buf)
    w.writerow(header)
    for n in nodes:
        if n.node_type == "campaign":
            w.writerow(["Sponsored Products", "Campaign", "Create", n.name, "", "", "",
                        "", n.budget, "enabled", "Manual", p.asin, n.note or ""])
        elif n.node_type == "adgroup":
            camp = by_id.get(n.parent_id)
            w.writerow(["Sponsored Products", "Ad Group", "Create", camp.name if camp else "",
                        n.name, "", "", n.bid, "", "enabled", "Manual", p.asin, n.note or ""])
        else:
            grp = by_id.get(n.parent_id)
            camp = by_id.get(grp.parent_id) if grp else None
            w.writerow(["Sponsored Products", "Keyword", "Create", camp.name if camp else "",
                        grp.name if grp else "", n.name, n.match_type, n.bid, "", "enabled",
                        "Manual", p.asin, n.note or ""])
    path = os.path.join(EXPORT_DIR, f"launch_{pid}_bulk.csv")
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        f.write(buf.getvalue())
    db.add(LaunchExport(project_id=pid, file_type="sp-bulk", file_path=path, row_count=len(nodes)))
    db.commit()
    return Response(content="\ufeff" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename=launch_{pid}_bulk.csv"})
