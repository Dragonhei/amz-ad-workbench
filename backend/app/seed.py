"""初始化种子数据：组织/店铺/账号、指标字典、默认规则、提示词、示例知识库。"""
import json
from datetime import date, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from .auth import hash_password
from .db import SessionLocal
from .metrics import METRICS
from .models import (AnalysisRule, KbBidRule, KbCompetitor, KbKeyword, KbRankTrack, LlmProvider,
                     MetricDefinition, Org, PromptTemplate, Shop, User)
from .rules import DEFAULT_PROMPT, DEFAULT_RULES


def _ensure_schema(db: Session):
    """兼容旧库：缺失列时补齐（SQLite 的 create_all 不会 ALTER 已存在的表）。"""
    cols = [r[1] for r in db.execute(text("PRAGMA table_info(shop)")).fetchall()]
    if "timezone" not in cols:
        db.execute(text("ALTER TABLE shop ADD COLUMN timezone VARCHAR(32) "
                        "DEFAULT 'America/New_York'"))
        db.commit()
    # P1-2：FactAdPerf 补齐 SB/SD 专用列（旧库升级兼容）
    fact_cols = {r[1] for r in db.execute(text("PRAGMA table_info(fact_ad_perf)")).fetchall()}
    for col, ctype in (
        ("landing_page_id", "VARCHAR(64)"),
        ("creative_id", "VARCHAR(64)"),
        ("headline", "VARCHAR(256)"),
        ("audience_id", "VARCHAR(64)"),
        ("placement", "VARCHAR(64)"),
        ("associated_asin", "VARCHAR(32)"),
    ):
        if col not in fact_cols:
            db.execute(text(f"ALTER TABLE fact_ad_perf ADD COLUMN {col} {ctype} DEFAULT ''"))
    if any(col not in fact_cols for col, _ in (
        ("landing_page_id", ""), ("creative_id", ""), ("headline", ""),
        ("audience_id", ""), ("placement", ""), ("associated_asin", ""))):
        db.commit()
    # P1-3：kb_rank_track 补齐 marketplace / rank_source 列（旧库升级兼容）
    rank_cols = {r[1] for r in db.execute(text("PRAGMA table_info(kb_rank_track)")).fetchall()}
    for col, ctype in (("marketplace", "VARCHAR(16)"), ("rank_source", "VARCHAR(16)")):
        if col not in rank_cols:
            db.execute(text(f"ALTER TABLE kb_rank_track ADD COLUMN {col} {ctype} DEFAULT ''"))
    if any(col not in rank_cols for col, _ in (("marketplace", ""), ("rank_source", ""))):
        db.commit()
    # P1-4：analysis_rule 补齐 dsl_text 列（旧库升级兼容）
    rule_cols = {r[1] for r in db.execute(text("PRAGMA table_info(analysis_rule)")).fetchall()}
    if "dsl_text" not in rule_cols:
        db.execute(text("ALTER TABLE analysis_rule ADD COLUMN dsl_text TEXT DEFAULT ''"))
        db.commit()
    # P1-5：action_item 补齐 executed / executed_at 列（旧库升级兼容，新表由 create_all 自动建）
    ai_cols = {r[1] for r in db.execute(text("PRAGMA table_info(action_item)")).fetchall()}
    if "executed" not in ai_cols:
        db.execute(text("ALTER TABLE action_item ADD COLUMN executed BOOLEAN DEFAULT 0"))
    if "executed_at" not in ai_cols:
        db.execute(text("ALTER TABLE action_item ADD COLUMN executed_at DATETIME"))
    if "executed" not in ai_cols or "executed_at" not in ai_cols:
        db.commit()


SEED_KEYWORDS = [
    ("shower curtain liner", "功能词", "high", "active", "B0C1"),
    ("fabric shower curtain", "核心词", "high", "active", "B0C1"),
    ("waterproof shower curtain", "属性词", "high", "active", "B0C1"),
    ("shower curtain with hooks", "组合词", "high", "active", "B0C1"),
    ("bathroom curtain 72 inch", "长尾词", "high", "watch", "B0C1"),
    ("hotel style shower curtain", "场景词", "high", "active", "B0C2"),
    ("mold resistant shower liner", "属性词", "high", "active", "B0C1"),
    ("clear shower curtain", "属性词", "medium", "watch", "B0C2"),
    ("shower curtain rings", "配件词", "low", "negative", ""),
    ("curtain rod", "无关词", "low", "negative", ""),
]


def seed_all(db: Session = None):
    db = db or SessionLocal()
    try:
        _ensure_schema(db)
        if not db.query(Org).get(1):
            db.add(Org(id=1, name="默认组织"))
        # 多店铺 / 多站点：逐店幂等确保（已存在则不重复插入，缺失时区则补正）
        SHOPS = [
            (1, "示例店铺 · 美国站", "US", "USD", "America/New_York"),
            (2, "示例店铺 · 德国站", "DE", "EUR", "Europe/Berlin"),
            (3, "示例店铺 · 英国站", "UK", "GBP", "Europe/London"),
        ]
        for sid, name, mp, cur, tz in SHOPS:
            ex = db.query(Shop).get(sid)
            if not ex:
                db.add(Shop(id=sid, org_id=1, name=name, marketplace=mp, currency=cur, timezone=tz))
            else:
                ex.timezone = tz   # 已知示例店铺：始终校正为正确站点时区
        if not db.query(User).filter(User.username == "admin").first():
            db.add(User(username="admin", password_hash=hash_password("admin123"),
                        full_name="系统管理员", role="admin", allowed_shop_ids="[]"))
        if not db.query(User).filter(User.username == "operator").first():
            db.add(User(username="operator", password_hash=hash_password("123456"),
                        full_name="运营小李", role="operator", allowed_shop_ids="[1]",
                        quota_tokens=500_000, quota_cost=50.0))
        for m in METRICS:
            if not db.query(MetricDefinition).get(m["code"]):
                db.add(MetricDefinition(code=m["code"], name_zh=m["name_zh"], formula=m["formula"],
                                        unit=m["unit"], higher_better=m["higher_better"]))
        for r in DEFAULT_RULES:
            if not db.query(AnalysisRule).filter(AnalysisRule.code == r["code"]).first():
                db.add(AnalysisRule(code=r["code"], name_zh=r["name_zh"], dimension=r["dimension"],
                                    condition_json=r["condition_json"],
                                    advice_template=r["advice_template"]))
        # P1-4：示例 DSL 规则（可视化规则引擎）。dsl_text 为空则代表属于内置 JSON 条件规则。
        SEED_DSL_RULES = [
            {
                # 当任意广告活动的 ACOS 超过 40% 时，给出竞价下调建议（中优先级，竞价调整维度）
                "code": "dsl_acos_campaign_high",
                "name_zh": "活动 ACOS 超阈值（DSL 示例）",
                "dimension": "bid",
                "dsl_text": 'WHEN acos > 40 FOR campaign THEN SUGGEST bid "活动「{scope}」ACOS 达 {value}%，'
                            '超过 {threshold}%，建议分两次下调竞价各 10~15%" WITH SEVERITY mid',
                "advice_template": "",
                "priority": 5,
            },
            {
                # 当任意关键词 CTR 低于 0.2% 时，给出 Listing 优化建议（低优先级，Listing 维度）
                "code": "dsl_ctr_keyword_low",
                "name_zh": "关键词 CTR 偏低（DSL 示例）",
                "dimension": "listing",
                "dsl_text": 'WHEN ctr < 0.2 FOR keyword THEN SUGGEST listing "关键词「{scope}」CTR 仅 {value}%，'
                            '低于 {threshold}%，优先优化主图与标题" WITH SEVERITY low',
                "advice_template": "",
                "priority": 5,
            },
        ]
        for r in SEED_DSL_RULES:
            if not db.query(AnalysisRule).filter(AnalysisRule.code == r["code"]).first():
                db.add(AnalysisRule(code=r["code"], name_zh=r["name_zh"], dimension=r["dimension"],
                                    condition_json="{}", dsl_text=r["dsl_text"],
                                    advice_template=r["advice_template"], priority=r["priority"]))
        if not db.query(PromptTemplate).filter(PromptTemplate.code == "default").first():
            db.add(PromptTemplate(code="default", name_zh="12 维分析提示词", content=DEFAULT_PROMPT))
        if not db.query(LlmProvider).first():
            db.add(LlmProvider(name="内置规则引擎（默认）", endpoint="https://api.openai.com/v1/chat/completions",
                               model="gpt-4o-mini", api_key_enc="",
                               params_json=json.dumps({"temperature": 0.2, "max_tokens": 4000}),
                               enabled=False, is_default=True))
        if db.query(KbKeyword).count() == 0:
            for term, intent, rel, st, asin in SEED_KEYWORDS:
                db.add(KbKeyword(shop_id=1, term=term, intent=intent, relevance=rel, status=st,
                                 asin=asin, updated_by="seed"))
        if db.query(KbBidRule).count() == 0:
            db.add(KbBidRule(shop_id=1, keyword="*", match_type="exact", placement="all",
                             base_cpc=0.85, min_cpc=0.25, max_cpc=2.4, step=0.1, note="类目通用基准"))
            db.add(KbBidRule(shop_id=1, keyword="shower curtain", match_type="exact",
                             base_cpc=1.15, min_cpc=0.4, max_cpc=3.0, step=0.1, note="核心大词"))
            db.add(KbBidRule(shop_id=1, keyword="shower curtain", match_type="broad",
                             base_cpc=0.7, min_cpc=0.25, max_cpc=1.8, step=0.05, note="广泛控价"))
        if db.query(KbCompetitor).count() == 0:
            db.add(KbCompetitor(shop_id=1, competitor_asin="B0X1111111", brand="HomeVibe",
                                price=19.99, rating=4.5, reviews=3821,
                                selling_points="三层防水 / 含12挂钩 / 机洗"))
            db.add(KbCompetitor(shop_id=1, competitor_asin="B0X2222222", brand="PureBath",
                                price=16.49, rating=4.3, reviews=1560,
                                selling_points="OEKO-TEX 认证 / 加重下摆"))
            db.add(KbCompetitor(shop_id=1, competitor_asin="B0X3333333", brand="LuxLinen",
                                price=27.90, rating=4.7, reviews=8420,
                                selling_points="华夫格纹 / 酒店同款 / 180 尺寸"))
        # P1-3：排名追踪示例（多日期历史，含一处明显掉落以演示预警）
        if db.query(KbRankTrack).count() == 0:
            today = date.today()
            # (shop_id, asin, term, marketplace, [(周偏移, 自然排名, 广告排名, 页码), ...])
            history = [
                (1, "B0C1", "shower curtain liner", "US",
                 [(5, 5, 3, 1), (4, 4, 3, 1), (3, 6, 4, 1), (2, 5, 4, 1), (1, 7, 5, 1), (0, 12, 6, 2)]),
                (1, "B0C1", "fabric shower curtain", "US",
                 [(5, 9, 0, 1), (4, 8, 0, 1), (3, 7, 0, 1), (2, 7, 0, 1), (1, 6, 0, 1), (0, 6, 0, 1)]),
                (2, "B0C2", "duschvorhang", "DE",
                 [(5, 11, 0, 1), (4, 10, 0, 1), (3, 12, 0, 1), (2, 9, 0, 1), (1, 8, 0, 1), (0, 14, 0, 2)]),
                (3, "B0C1", "shower curtain", "UK",
                 [(5, 6, 4, 1), (4, 6, 4, 1), (3, 5, 3, 1), (2, 5, 3, 1), (1, 5, 3, 1), (0, 4, 2, 1)]),
            ]
            for sid, asin, term, mp, pts in history:
                for off, org, ad, pg in pts:
                    d = today - timedelta(weeks=off)
                    db.add(KbRankTrack(shop_id=sid, asin=asin, term=term, marketplace=mp,
                                       rank_source="seed", track_date=d,
                                       organic_rank=org, ad_rank=ad, page=pg))
        db.commit()
    finally:
        db.close()
