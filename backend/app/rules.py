"""12 维分析维度、内置规则引擎（无 LLM 时兜底）与默认提示词。"""
from sqlalchemy import func

from .models import (FactAdPerf, FactSearchTerm, FactAba, FactListingDaily, FactInventory,
                     KbKeyword, KbBidRule, KbCompetitor)
from .metrics import aggregate, calc_metrics, period_totals

DIMENSIONS = [
    {"code": "budget", "name_zh": "预算分配"},
    {"code": "bid", "name_zh": "竞价调整"},
    {"code": "keyword_add", "name_zh": "关键词增删"},
    {"code": "negative", "name_zh": "否定词"},
    {"code": "placement", "name_zh": "广告位"},
    {"code": "structure", "name_zh": "投放结构"},
    {"code": "listing", "name_zh": "Listing 优化"},
    {"code": "inventory", "name_zh": "库存联动"},
    {"code": "schedule", "name_zh": "节奏排期"},
    {"code": "competitor", "name_zh": "竞品应对"},
    {"code": "risk", "name_zh": "风险预警"},
    {"code": "review", "name_zh": "效果复盘"},
]

DEFAULT_PROMPT = """你是资深亚马逊广告投放专家。基于以下数据摘要，输出结构化的 12 维行动方案。

【店铺与周期】
店铺：{shop_name}｜周期：{date_start} ~ {date_end}｜目标 ACOS：{target_acos}%
币种与站点：{marketplace}

【整体指标】
{summary_text}

【分层明细（Top N）】
{top_rows}

【搜索词表现（Top N）】
{search_terms}

【规则预检命中】
{rule_hits}

【知识库参考】
关键词库命中：{kb_keywords}
竞价基准：{kb_bids}

【输出要求】
1. 只输出 JSON，结构：{"items":[{"dimension":"预算分配|竞价调整|关键词增删|否定词|广告位|投放结构|Listing 优化|库存联动|节奏排期|竞品应对|风险预警|效果复盘","title":"","detail":"","action":"","expected_impact":"","priority":"P0|P1|P2","confidence":0.0-1.0,"evidence":[{"metric_path":"","snapshot":""}]}]}
2. 12 个维度每个最多 2 条，总计不超过 18 条，按可执行性排序。
3. 每条必须给出可量化的动作（具体升降百分比、具体关键词、具体预算数字）。
4. evidence 必须引用上面给出的真实数字，禁止编造未出现的数据。
5. 使用简体中文。
"""

DEFAULT_RULES = [
    {"code": "high_spend_zero_order", "name_zh": "高花费零出单词", "dimension": "negative",
     "condition_json": '{"min_spend": 10, "orders": 0}',
     "advice_template": "花费 ≥ {min_spend} 且零订单，建议否定或降价 30%"},
    {"code": "acos_over_target", "name_zh": "ACOS 超目标", "dimension": "bid",
     "condition_json": '{"acos_multiplier": 1.5}',
     "advice_template": "ACOS 超过目标的 {acos_multiplier} 倍，建议竞价下调 15%"},
    {"code": "low_ctr", "name_zh": "低点击率", "dimension": "listing",
     "condition_json": '{"max_ctr": 0.35}',
     "advice_template": "CTR 低于 {max_ctr}%，优先优化主图与标题"},
    {"code": "low_cvr", "name_zh": "低转化率", "dimension": "listing",
     "condition_json": '{"max_cvr": 8}',
     "advice_template": "CVR 低于 {max_cvr}%，检查价格、评论、五点描述与 A+"},
    {"code": "inventory_risk", "name_zh": "库存告急", "dimension": "inventory",
     "condition_json": '{"days_cover": 14}',
     "advice_template": "库存可支撑不足 {days_cover} 天，建议下调预算并加快补货"},
    {"code": "budget_concentration", "name_zh": "预算过度集中", "dimension": "structure",
     "condition_json": '{"max_share": 50}',
     "advice_template": "单一活动花费占比超过 {max_share}%，建议拆分结构降低风险"},
    {"code": "aba_unused", "name_zh": "ABA 高潜词未投放", "dimension": "keyword_add",
     "condition_json": '{"max_rank": 100}',
     "advice_template": "存在排名前 {max_rank} 且未投放的高潜词，建议新增精准投放"},
]


# ---------------------------------------------------------------- 规则引擎
def _safe_div(a, b):
    return (a / b) if b else 0.0


def run_rules(db, shop_id, d1, d2, target_acos=35.0, params=None):
    """基于真实聚合数据产出 12 维结论，每条带 evidence。"""
    params = params or {}
    items = []
    agg_kw = aggregate(db, shop_id, d1, d2, group_by="keyword",
                       filters={"min_clicks": params.get("min_clicks", 5)})
    agg_camp = aggregate(db, shop_id, d1, d2, group_by="campaign")
    summary = agg_camp["summary"]
    total_sales = period_totals(db, shop_id, d1, d2)

    def ev(metric_path, snap, rows=""):
        return {"metric_path": metric_path, "snapshot": str(snap)[:800], "source_rows": str(rows)[:300]}

    # 1) 否定词 / 竞价：高花费零订单
    bad = [r for r in agg_kw["rows"] if r["orders"] == 0 and r["spend"] >= 10]
    bad.sort(key=lambda x: -x["spend"])
    if bad:
        top = bad[:8]
        spend_sum = round(sum(t["spend"] for t in top), 2)
        items.append({
            "dimension": "negative", "priority": "P0", "confidence": 0.9,
            "title": f"{len(bad)} 个关键词花费 ≥ $10 且零出单，累计浪费 ${spend_sum}",
            "detail": "、".join(f"{t['keyword_text']}(${t['spend']}/{t['clicks']}次点击)" for t in top[:5]),
            "action": "零单且点击 ≥ 10 的词添加精准否定；点击 5~10 的词保留观察并降价 30%；"
                      "将节省预算转移到 ACOS 低于目标词的投放上。",
            "expected_impact": f"预计回收 ${round(spend_sum * 0.6, 2)} 无效花费，整体 ACOS 下降 "
                               f"{round(_safe_div(spend_sum * 0.6, summary['sales'] or 1) * 100, 2)} 个百分点",
            "evidence": ev("fact_ad_perf.keyword[orders=0 & spend>=10]",
                           {"count": len(bad), "spend_sum": spend_sum, "top": top[:5]}),
        })

    # 2) 竞价调整：ACOS 超目标
    over = [r for r in agg_camp["rows"]
            if r["sales"] > 0 and r["acos"] > target_acos * 1.5 and r["spend"] > 5]
    over.sort(key=lambda x: -x["spend"])
    if over:
        t = over[0]
        items.append({
            "dimension": "bid", "priority": "P0", "confidence": 0.82,
            "title": f"{len(over)} 个活动 ACOS 超过目标 {target_acos}% 的 1.5 倍，"
                     f"代表活动「{t['campaign_name']}」ACOS {t['acos']}%",
            "detail": "、".join(f"{c['campaign_name']}(ACOS {c['acos']}%, 花费 ${c['spend']})"
                                for c in over[:5]),
            "action": f"对 ACOS > {round(target_acos * 1.5, 1)}% 的活动分两次下调竞价，每次 10~15%，"
                      f"间隔 3 天观察；单次降幅不超过 20% 以免流量断崖。",
            "expected_impact": f"按 CPC 下降 12% 估算，同等预算可多获得约 14% 点击",
            "evidence": ev("fact_ad_perf.campaign[acos>1.5*target]",
                           {"target_acos": target_acos, "count": len(over), "top": over[:5]}),
        })

    # 3) 预算分配：高转化低曝光
    good = [r for r in agg_kw["rows"]
            if r["sales"] > 0 and r["acos"] <= target_acos and r["impressions"] < 2000 and r["clicks"] >= 3]
    good.sort(key=lambda x: (x["acos"] or 999))
    if good:
        t = good[0]
        items.append({
            "dimension": "budget", "priority": "P1", "confidence": 0.78,
            "title": f"{len(good)} 个高效词曝光不足 2000，如「{t['keyword_text']}」"
                     f"ACOS 仅 {t['acos']}%",
            "detail": "、".join(f"{g['keyword_text']}(ACOS {g['acos']}%, 曝光 {g['impressions']})"
                                for g in good[:5]),
            "action": "把这些词单独建组并提高竞价 15~20%，同时把否定词释放出的预算按 6:4 分配到"
                      "高效词组与自动词组。",
            "expected_impact": "高效词曝光提升 30~50%，整体 ACOS 有望下降 2~4 个百分点",
            "evidence": ev("fact_ad_perf.keyword[acos<=target & impressions<2000]",
                           {"count": len(good), "top": good[:5]}),
        })

    # 4) 搜索词：高点击无转化
    st_rows = (db.query(FactSearchTerm.search_term,
                        func.sum(FactSearchTerm.clicks).label("clicks"),
                        func.sum(FactSearchTerm.spend).label("spend"),
                        func.sum(FactSearchTerm.orders).label("orders"),
                        func.sum(FactSearchTerm.sales).label("sales"))
               .filter(FactSearchTerm.shop_id == shop_id)
               .filter(FactSearchTerm.date >= d1, FactSearchTerm.date <= d2)
               .group_by(FactSearchTerm.search_term).all())
    st_bad = [r for r in st_rows if (r.clicks or 0) >= 8 and (r.orders or 0) == 0]
    st_bad.sort(key=lambda r: -(r.spend or 0))
    if st_bad:
        top = st_bad[:8]
        items.append({
            "dimension": "negative", "priority": "P1", "confidence": 0.85,
            "title": f"{len(st_bad)} 个搜索词点击 ≥ 8 且零转化，累计花费 "
                     f"${round(sum(t.spend or 0 for t in top), 2)}",
            "detail": "、".join(f"{t.search_term}({t.clicks}点击/${round(t.spend or 0, 2)})" for t in top[:5]),
            "action": "确认与产品无关后添加词组否定；相关性高的词改为精准匹配单独控价。",
            "expected_impact": f"预计减少 ${round(sum(t.spend or 0 for t in top) * 0.7, 2)} 无效花费",
            "evidence": ev("fact_search_term[clicks>=8 & orders=0]",
                           {"count": len(st_bad), "top": [t.search_term for t in top[:5]]}),
        })
    st_gold = [r for r in st_rows if (r.orders or 0) >= 1 and (r.sales or 0) > 0
               and _safe_div(r.spend or 0, r.sales) * 100 <= target_acos]
    if st_gold:
        st_gold.sort(key=lambda r: -(r.sales or 0))
        items.append({
            "dimension": "keyword_add", "priority": "P1", "confidence": 0.8,
            "title": f"{len(st_gold)} 个高转化搜索词尚未加入关键词投放",
            "detail": "、".join(f"{t.search_term}({t.orders}单/${round(t.sales or 0, 2)})"
                                for t in st_gold[:5]),
            "action": "按搜索词原样新建精准匹配关键词，初始竞价取该词 CPC 的 1.1 倍，"
                      "并在原活动中加为精准否定避免内耗。",
            "expected_impact": "高效流量归因更清晰，便于单独控价与扩量",
            "evidence": ev("fact_search_term[orders>=1 & acos<=target]",
                           {"count": len(st_gold), "top": [t.search_term for t in st_gold[:5]]}),
        })

    # 5) Listing 优化：CTR / CVR
    if summary["impressions"] and summary["ctr"] < params.get("max_ctr", 0.35):
        items.append({
            "dimension": "listing", "priority": "P1", "confidence": 0.72,
            "title": f"整体 CTR 仅 {summary['ctr']}%，低于 {params.get('max_ctr', 0.35)}% 参考线",
            "detail": f"曝光 {summary['impressions']}、点击 {summary['clicks']}、"
                      f"CPC ${summary['cpc']}，CTR 偏低通常意味着主图或标题相关性不足。",
            "action": "A/B 测试主图（首图白底+场景卖点）、标题前置核心关键词与规格；"
                      "同步检查价格与配送方式是否明显弱于竞品。",
            "expected_impact": "CTR 提升 0.1 个百分点约可增加 25~30% 点击量",
            "evidence": ev("fact_ad_perf.summary.ctr", summary),
        })
    if summary["clicks"] and summary["cvr"] < params.get("max_cvr", 8):
        items.append({
            "dimension": "listing", "priority": "P1", "confidence": 0.7,
            "title": f"整体 CVR 为 {summary['cvr']}%，低于 {params.get('max_cvr', 8)}% 参考线",
            "detail": f"点击 {summary['clicks']}、订单 {summary['orders']}，"
                      f"CTR 正常但转化不足，问题多半在详情页与竞争环境。",
            "action": "优化五点描述与 A+ 内容，补齐对比图与尺寸图；"
                      "配合优惠券提升首单转化；核查评论区近期差评。",
            "expected_impact": "CVR 提升 2 个百分点约可降低 ACOS 3~5 个百分点",
            "evidence": ev("fact_ad_perf.summary.cvr", summary),
        })

    # 6) 库存联动（基于 FactInventory 最新快照，逐 ASIN 联动广告）
    inv_rows = (db.query(FactInventory)
                .filter(FactInventory.shop_id == shop_id,
                        FactInventory.date >= d1, FactInventory.date <= d2).all())
    num_days = max((d2 - d1).days + 1, 1)
    if inv_rows:
        latest = {}
        for r in inv_rows:
            key = (r.shop_id, r.asin)
            if key not in latest or r.date > latest[key].date:
                latest[key] = r
        ld = (db.query(FactListingDaily.asin, func.sum(FactListingDaily.units).label("units"))
              .filter(FactListingDaily.shop_id == shop_id, FactListingDaily.date >= d1,
                      FactListingDaily.date <= d2, FactListingDaily.asin != "")
              .group_by(FactListingDaily.asin).all())
        ld_units = {x.asin: (x.units or 0) for x in ld}
        sd_asins = {a.associated_asin for a in db.query(FactAdPerf).filter(
            FactAdPerf.shop_id == shop_id, FactAdPerf.associated_asin != "").all()}
        threshold = params.get("days_cover", 14)
        low, crit = [], []
        for (sid, asin), rec in latest.items():
            du = _safe_div(ld_units.get(asin, 0), num_days)
            cover = (rec.days_of_cover if (rec.days_of_cover or 0) > 0
                     else (_safe_div(rec.qty, du) if du else 0))
            advertised = (ld_units.get(asin, 0) > 0) or (asin in sd_asins)
            if 0 < cover < threshold:
                entry = {"asin": asin, "qty": rec.qty, "inbound": rec.inbound,
                         "cover": round(cover, 1), "advertised": advertised}
                (crit if advertised else low).append(entry)
        if crit:
            worst = min(crit, key=lambda x: x["cover"])
            items.append({
                "dimension": "inventory", "priority": "P0", "confidence": 0.9,
                "title": f"{len(crit)} 个在投 ASIN 库存告急，仅可支撑 {worst['cover']}~"
                         f"{max(x['cover'] for x in crit)} 天",
                "detail": "、".join(f"{c['asin']}(剩{c['qty']}件/{c['cover']}天，在途{c['inbound']})"
                                    for c in sorted(crit, key=lambda x: x["cover"])[:6]),
                "action": "立即下调这些 ASIN 对应活动预算 20~30% 避免断货期空烧；"
                          "同步安排补货，到货前把预算倾斜给库存充足的 ASIN。",
                "expected_impact": "避免断货导致的排名与权重损失（恢复成本通常为断货期广告费的 3~5 倍）",
                "evidence": ev("fact_inventory + fact_listing_daily.asin[days_cover<14 & advertised]",
                               {"threshold": threshold, "critical": crit[:6]}),
            })
        if low:
            items.append({
                "dimension": "inventory", "priority": "P2", "confidence": 0.8,
                "title": f"{len(low)} 个 ASIN 可售天数低于 {threshold} 天（暂无在投广告）",
                "detail": "、".join(f"{x['asin']}(剩{x['qty']}件/{x['cover']}天)" for x in low[:6]),
                "action": "虽无在投广告，仍建议提前补货以防旺季断货；可在到货后再启动投放。",
                "expected_impact": "维持可售率，避免有单无货",
                "evidence": ev("fact_inventory[days_cover<14 & not advertised]",
                               {"threshold": threshold, "low": low[:6]}),
            })
    else:
        # 回退：仅业务报告库存总量时的粗估（兼容未上传库存报表的场景）
        inv = (db.query(func.sum(FactListingDaily.inventory), func.sum(FactListingDaily.units))
               .filter(FactListingDaily.shop_id == shop_id,
                       FactListingDaily.date >= d1, FactListingDaily.date <= d2).first())
        if inv and inv[0]:
            daily_units = _safe_div(inv[1] or 0, num_days)
            cover = _safe_div(inv[0], daily_units or 1)
            if 0 < cover < params.get("days_cover", 14):
                items.append({
                    "dimension": "inventory", "priority": "P0", "confidence": 0.85,
                    "title": f"库存仅可支撑约 {round(cover, 1)} 天（日均 {round(daily_units, 1)} 件）",
                    "detail": f"期间库存合计 {int(inv[0])} 件，销量 {int(inv[1] or 0)} 件。",
                    "action": "立即下调高效活动预算 20~30% 避免断货期空烧；同步安排补货，"
                              "到货前把预算倾斜给库存充足的 ASIN。",
                    "expected_impact": "避免断货导致的排名与权重损失（恢复成本通常为断货期广告费的 3~5 倍）",
                    "evidence": ev("fact_listing_daily.inventory / daily_units",
                                   {"inventory": int(inv[0]), "units": int(inv[1] or 0),
                                    "cover_days": round(cover, 1)}),
                })

    # 7) 结构风险：花费集中
    if agg_camp["rows"] and summary["spend"]:
        top_camp = max(agg_camp["rows"], key=lambda r: r["spend"])
        share = _safe_div(top_camp["spend"], summary["spend"]) * 100
        if share > params.get("max_share", 50):
            items.append({
                "dimension": "structure", "priority": "P2", "confidence": 0.75,
                "title": f"活动「{top_camp['campaign_name']}」占总花费 {round(share, 1)}%，结构过于集中",
                "detail": f"该活动花费 ${top_camp['spend']}，ACOS {top_camp['acos']}%。",
                "action": "按匹配方式或词根拆分为 2~3 个活动，分别设置预算与竞价策略，"
                          "避免单活动预算耗尽拖累整体。",
                "expected_impact": "拆分后可单独控价，预算利用率提升 10~20%",
                "evidence": ev("fact_ad_perf.campaign.spend_share",
                               {"campaign": top_camp["campaign_name"], "share_pct": round(share, 1)}),
            })

    # 8) ABA 高潜词
    kw_existing = {k.term.lower() for k in db.query(KbKeyword).filter(
        KbKeyword.shop_id.in_([shop_id, 0])).all()}
    aba = (db.query(FactAba).filter(FactAba.shop_id == shop_id)
           .order_by(FactAba.search_rank).limit(200).all())
    aba_gap = [a for a in aba if a.search_term.lower() not in kw_existing
               and (a.search_rank or 9999) <= params.get("max_rank", 100)]
    if aba_gap:
        items.append({
            "dimension": "keyword_add", "priority": "P2", "confidence": 0.68,
            "title": f"ABA 排名前 {params.get('max_rank', 100)} 中有 {len(aba_gap)} 个词尚未进入投放/关键词库",
            "detail": "、".join(f"{a.search_term}(#{a.search_rank})" for a in aba_gap[:6]),
            "action": "挑选与产品强相关的词新建精准匹配，初始竞价取类目 CPC 基准的 0.9 倍，"
                      "两周后按 CVR 决定是否提价。",
            "expected_impact": "补充高潜流量入口，通常 2~4 周内带来增量订单",
            "evidence": ev("fact_aba[rank<=100] - kb_keyword",
                           {"count": len(aba_gap), "top": [a.search_term for a in aba_gap[:6]]}),
        })

    # 9) 广告位（无广告位报表时的推断建议）
    if summary["clicks"]:
        items.append({
            "dimension": "placement", "priority": "P2", "confidence": 0.6,
            "title": "缺少广告位维度数据，暂按整体表现给出加价建议",
            "detail": f"整体 CPC ${summary['cpc']}、ACOS {summary['acos']}%、ROAS {summary['roas']}。",
            "action": "上传广告位报表后可精确调价；当前建议：搜索结果顶部加价 20%，"
                      "商品详情页保持默认，其余位置不加价。若整体 ACOS 已超标则整体下调 10%。",
            "expected_impact": "顶部流量转化通常高出 30~60%，加价后有望改善整体 ACOS",
            "evidence": ev("fact_ad_perf.summary.cpc/acos", summary),
        })

    # 10) 节奏排期：按周内波动
    trend = aggregate(db, shop_id, d1, d2, group_by="date", limit=100000)["rows"]
    if len(trend) >= 7:
        by_dow = {}
        import datetime as _dt
        for r in trend:
            try:
                d = _dt.date.fromisoformat(r["date"])
            except (ValueError, TypeError):
                continue
            by_dow.setdefault(d.weekday(), []).append(r)
        if len(by_dow) >= 5:
            avg = {k: sum(x["spend"] for x in v) / len(v) for k, v in by_dow.items()}
            best = max(avg, key=lambda k: avg[k])
            worst = min(avg, key=lambda k: avg[k])
            names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
            items.append({
                "dimension": "schedule", "priority": "P2", "confidence": 0.6,
                "title": f"周内花费分布不均：{names[best]}均值最高 ${round(avg[best], 2)}，"
                         f"{names[worst]}最低 ${round(avg[worst], 2)}",
                "detail": "；".join(f"{names[k]} ${round(v, 2)}" for k, v in sorted(avg.items())),
                "action": "把预算向高效时段倾斜，低效日下调 20%；促销日提前 2 天上调预算 30%，"
                          "结束后 1 天内回落，避免惯性超支。",
                "expected_impact": "预算利用率提升 5~15%",
                "evidence": ev("fact_ad_perf.daily.by_weekday",
                               {names[k]: round(v, 2) for k, v in avg.items()}),
            })

    # 11) 竞品应对
    comps = db.query(KbCompetitor).filter(KbCompetitor.shop_id.in_([shop_id, 0])).all()
    if comps:
        lowest = min(comps, key=lambda c: c.price or 9e9)
        items.append({
            "dimension": "competitor", "priority": "P2", "confidence": 0.62,
            "title": f"竞品库 {len(comps)} 个 ASIN，最低价 ${lowest.price}（{lowest.brand or '未知品牌'}）",
            "detail": "；".join(f"{c.competitor_asin} ${c.price} / {c.rating}分 / {c.reviews}评论"
                                for c in comps[:4]),
            "action": "对价格明显低于我方的竞品 ASIN 投放商品定位（SD/SP 商品投放），"
                      "主推差异化卖点；价格差距较大时改用优惠券而非直接降价。",
            "expected_impact": "拦截对比流量，提升该类目下的曝光占比",
            "evidence": ev("kb_competitor",
                           {"count": len(comps), "lowest_price": lowest.price,
                            "lowest_asin": lowest.competitor_asin}),
        })

    # 12) 效果复盘
    items.append({
        "dimension": "review", "priority": "P1", "confidence": 0.9,
        "title": f"周期复盘：花费 ${summary['spend']}、销售额 ${summary['sales']}、"
                 f"ACOS {summary['acos']}%、TACOS {summary['tacos']}%",
        "detail": f"曝光 {summary['impressions']}、点击 {summary['clicks']}、CTR {summary['ctr']}%、"
                  f"订单 {summary['orders']}、CVR {summary['cvr']}%、CPC ${summary['cpc']}、"
                  f"ROAS {summary['roas']}。目标 ACOS {target_acos}%。",
        "action": "按 P0 → P1 → P2 顺序执行，每条改动间隔 3 天并记录前后指标；"
                  "下周同一时间对比 ACOS、TACOS、订单量三项核心指标。",
        "expected_impact": f"若 P0 项全部落地，预计整体 ACOS 向 {target_acos}% 目标收敛",
        "evidence": ev("fact_ad_perf.summary", {**summary, "total_sales": round(total_sales, 2)}),
    })

    # 13) 风险预警
    risks = []
    if summary["spend"] and summary["sales"] == 0:
        risks.append("周期内零广告销售额，需立即检查 Listing 状态与库存")
    if summary["spend"] > 0 and summary["acos"] > target_acos * 2:
        risks.append(f"整体 ACOS {summary['acos']}% 已达目标 2 倍以上")
    if not agg_camp["rows"]:
        risks.append("所选周期内无广告数据，请确认报表已上传并完成解析")
    if risks:
        items.append({
            "dimension": "risk", "priority": "P0", "confidence": 0.9,
            "title": "；".join(risks),
            "detail": f"目标 ACOS {target_acos}%，实际 {summary['acos']}%。",
            "action": "先止血（暂停或大幅降价低效活动），再逐项排查 Listing、库存与竞争环境。",
            "expected_impact": "避免亏损扩大",
            "evidence": ev("fact_ad_perf.summary.risk", {"risks": risks, "summary": summary}),
        })
    return items
