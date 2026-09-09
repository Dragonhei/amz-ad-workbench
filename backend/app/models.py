"""核心数据模型：平台 / 接入 / 事实 / 派生 / 分析 / 知识库 / 冷启动 七层。"""
from datetime import datetime, date

from sqlalchemy import (Column, Integer, String, Float, Date, DateTime, Text, Boolean,
                        ForeignKey, UniqueConstraint, Index)

from .db import Base


def utcnow():
    return datetime.utcnow()


# ---------------------------------------------------------------- 平台层
class Org(Base):
    __tablename__ = "org"
    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=utcnow)


class Shop(Base):
    __tablename__ = "shop"
    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("org.id"), default=1)
    name = Column(String(128), nullable=False)
    marketplace = Column(String(16), default="US")        # US|DE|UK|JP|FR|...
    currency = Column(String(8), default="USD")           # USD|EUR|GBP|JPY|...
    timezone = Column(String(32), default="America/New_York",
                      server_default="America/New_York")  # 站点时区，报表周期按站点对齐
    created_at = Column(DateTime, default=utcnow)


class User(Base):
    __tablename__ = "user"
    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    full_name = Column(String(64), default="")
    role = Column(String(16), default="operator")          # admin | operator
    status = Column(String(16), default="active")
    allowed_shop_ids = Column(Text, default="[]")          # JSON 数组，数据权限
    quota_tokens = Column(Integer, default=2_000_000)      # 每月 token 配额
    quota_cost = Column(Float, default=200.0)              # 每月金额配额（元/美元）
    created_at = Column(DateTime, default=utcnow)


class UsageLog(Base):
    __tablename__ = "usage_log"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"))
    shop_id = Column(Integer, nullable=True)
    ts = Column(DateTime, default=utcnow)
    run_type = Column(String(32), default="analysis")
    provider = Column(String(64), default="rule-engine")
    model = Column(String(64), default="")
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    cost = Column(Float, default=0.0)
    status = Column(String(16), default="success")
    message = Column(Text, default="")


class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True)
    ts = Column(DateTime, default=utcnow)
    user_id = Column(Integer, nullable=True)
    action = Column(String(64))
    target = Column(String(128), default="")
    detail = Column(Text, default="")


# ---------------------------------------------------------------- 接入层
class SourceFile(Base):
    __tablename__ = "source_file"
    id = Column(Integer, primary_key=True)
    shop_id = Column(Integer, nullable=False)
    file_name = Column(String(256))
    file_hash = Column(String(64), index=True)
    size = Column(Integer, default=0)
    storage_path = Column(String(512), default="")
    uploader = Column(String(64), default="")
    created_at = Column(DateTime, default=utcnow)


class IngestJob(Base):
    __tablename__ = "ingest_job"
    id = Column(Integer, primary_key=True)
    source_file_id = Column(Integer, ForeignKey("source_file.id"))
    shop_id = Column(Integer, nullable=False)
    report_type = Column(String(16))          # 最终采用的类型（可手工覆盖）
    detected_type = Column(String(16))        # 自动识别结果
    confidence = Column(Float, default=0.0)
    date_start = Column(Date, nullable=True)
    date_end = Column(Date, nullable=True)
    row_total = Column(Integer, default=0)
    row_ok = Column(Integer, default=0)
    row_err = Column(Integer, default=0)
    status = Column(String(16), default="preview")   # preview | success | failed | partial
    strategy = Column(String(16), default="append")  # append | overwrite | skip
    parser_version = Column(String(16), default="1.0")
    message = Column(Text, default="")
    operator = Column(String(64), default="")
    created_at = Column(DateTime, default=utcnow)


class FieldMapping(Base):
    __tablename__ = "field_mapping"
    id = Column(Integer, primary_key=True)
    shop_id = Column(Integer, default=0)      # 0 = 全局内置模板
    report_type = Column(String(16))
    canonical_field = Column(String(64))
    raw_header = Column(String(256))
    updated_at = Column(DateTime, default=utcnow)
    __table_args__ = (UniqueConstraint("shop_id", "report_type", "canonical_field", name="uq_mapping"),)


class ParseIssue(Base):
    __tablename__ = "parse_issue"
    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("ingest_job.id"))
    row_no = Column(Integer, default=0)
    severity = Column(String(16), default="warning")   # blocking | warning
    column_name = Column(String(128), default="")
    raw_value = Column(Text, default="")
    message = Column(Text, default="")


class DatasetVersion(Base):
    """数据版本：同 店铺+报表类型+周期 唯一，支持覆盖与回溯。"""
    __tablename__ = "dataset_version"
    id = Column(Integer, primary_key=True)
    shop_id = Column(Integer, nullable=False)
    report_type = Column(String(16))
    period_start = Column(Date, nullable=True)
    period_end = Column(Date, nullable=True)
    job_id = Column(Integer, nullable=True)
    row_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    superseded_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=utcnow)


# ---------------------------------------------------------------- 事实层
class FactAdPerf(Base):
    """统一 canonical 广告事实表：SP/SB/SD 共用。"""
    __tablename__ = "fact_ad_perf"
    id = Column(Integer, primary_key=True)
    shop_id = Column(Integer, nullable=False)
    date = Column(Date, nullable=False)
    ad_format = Column(String(8), default="SP")
    level = Column(String(16), default="campaign")   # campaign | adgroup | keyword
    campaign_id = Column(String(64), default="")
    campaign_name = Column(String(256), default="")
    adgroup_id = Column(String(64), default="")
    adgroup_name = Column(String(256), default="")
    keyword_id = Column(String(64), default="")
    keyword_text = Column(String(256), default="")
    match_type = Column(String(16), default="")
    targeting = Column(String(256), default="")
    # SB/SD 专用维度（SP 报表留空）
    landing_page_id = Column(String(64), default="")    # SB 落地页
    creative_id = Column(String(64), default="")        # SB 创意
    headline = Column(String(256), default="")          # SB 标题
    audience_id = Column(String(64), default="")        # SD 受众
    placement = Column(String(64), default="")          # 投放位置（Top of Search / Product Pages…）
    associated_asin = Column(String(32), default="")    # SD 商品定向 ASIN
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    spend = Column(Float, default=0.0)
    orders = Column(Integer, default=0)
    units = Column(Integer, default=0)
    sales = Column(Float, default=0.0)
    version_id = Column(Integer, nullable=True)
    __table_args__ = (Index("ix_fact_ad_shop_date", "shop_id", "date"),
                      Index("ix_fact_ad_camp", "shop_id", "campaign_id"),
                      Index("ix_fact_ad_kw", "shop_id", "keyword_text"))


class FactSearchTerm(Base):
    __tablename__ = "fact_search_term"
    id = Column(Integer, primary_key=True)
    shop_id = Column(Integer, nullable=False)
    date = Column(Date, nullable=False)
    campaign_id = Column(String(64), default="")
    campaign_name = Column(String(256), default="")
    adgroup_id = Column(String(64), default="")
    adgroup_name = Column(String(256), default="")
    search_term = Column(String(256), default="")
    match_type = Column(String(16), default="")
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    spend = Column(Float, default=0.0)
    orders = Column(Integer, default=0)
    sales = Column(Float, default=0.0)
    version_id = Column(Integer, nullable=True)
    __table_args__ = (Index("ix_fact_st_shop_date", "shop_id", "date"),)


class FactAba(Base):
    __tablename__ = "fact_aba"
    id = Column(Integer, primary_key=True)
    shop_id = Column(Integer, nullable=False)
    week_start = Column(Date, nullable=False)
    search_term = Column(String(256), default="")
    search_rank = Column(Integer, default=0)
    top3_click_share = Column(Float, default=0.0)
    top3_conv_share = Column(Float, default=0.0)
    version_id = Column(Integer, nullable=True)


class FactBrandMetric(Base):
    __tablename__ = "fact_brand_metric"
    id = Column(Integer, primary_key=True)
    shop_id = Column(Integer, nullable=False)
    date = Column(Date, nullable=False)
    asin = Column(String(32), default="")
    brand_search_volume = Column(Integer, default=0)
    new_to_brand_orders = Column(Integer, default=0)
    new_to_brand_pct = Column(Float, default=0.0)
    repeat_purchase_pct = Column(Float, default=0.0)
    version_id = Column(Integer, nullable=True)


class FactListingDaily(Base):
    """业务报告：TACOS 分母、库存联动依赖此表。"""
    __tablename__ = "fact_listing_daily"
    id = Column(Integer, primary_key=True)
    shop_id = Column(Integer, nullable=False)
    date = Column(Date, nullable=False)
    asin = Column(String(32), default="")
    sessions = Column(Integer, default=0)
    page_views = Column(Integer, default=0)
    units = Column(Integer, default=0)
    orders = Column(Integer, default=0)
    total_sales = Column(Float, default=0.0)
    inventory = Column(Integer, default=0)
    version_id = Column(Integer, nullable=True)
    __table_args__ = (Index("ix_fact_ld_shop_date", "shop_id", "date"),)


class FactInventory(Base):
    """库存事实表：按 ASIN / 日期记录可售库存、在途与可售天数（P1-6 库存联动预警）。"""
    __tablename__ = "fact_inventory"
    id = Column(Integer, primary_key=True)
    shop_id = Column(Integer, nullable=False)
    date = Column(Date, nullable=False)
    asin = Column(String(32), default="")
    sku = Column(String(64), default="")
    qty = Column(Integer, default=0)               # 可售库存
    inbound = Column(Integer, default=0)            # 在途 / 已发货至 FBA
    daily_sales = Column(Float, default=0.0)        # 当日销量（用于计算可售天数）
    days_of_cover = Column(Float, default=0.0)      # 可售天数 = qty / 日均销量
    version_id = Column(Integer, nullable=True)
    __table_args__ = (Index("ix_fact_inv_shop_date", "shop_id", "date"),
                      Index("ix_fact_inv_asin", "shop_id", "asin"))


# ---------------------------------------------------------------- 派生层
class MetricDefinition(Base):
    __tablename__ = "metric_definition"
    code = Column(String(32), primary_key=True)
    name_zh = Column(String(64))
    formula = Column(String(256))
    unit = Column(String(16), default="")
    higher_better = Column(Boolean, default=True)


# ---------------------------------------------------------------- 分析层
class LlmProvider(Base):
    __tablename__ = "llm_provider"
    id = Column(Integer, primary_key=True)
    name = Column(String(64), default="default")
    endpoint = Column(String(512), default="https://api.openai.com/v1/chat/completions")
    model = Column(String(128), default="gpt-4o-mini")
    api_key_enc = Column(Text, default="")     # 简单可逆混淆存储，仅回显掩码
    params_json = Column(Text, default='{"temperature":0.2,"max_tokens":4000}')
    enabled = Column(Boolean, default=False)
    is_default = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=utcnow)


class AnalysisRule(Base):
    __tablename__ = "analysis_rule"
    id = Column(Integer, primary_key=True)
    code = Column(String(64), unique=True)
    name_zh = Column(String(128))
    dimension = Column(String(32))             # 12 维之一
    condition_json = Column(Text, default="{}")
    priority = Column(Integer, default=5)
    enabled = Column(Boolean, default=True)
    advice_template = Column(Text, default="")


class PromptTemplate(Base):
    __tablename__ = "prompt_template"
    id = Column(Integer, primary_key=True)
    code = Column(String(64), unique=True)
    name_zh = Column(String(128))
    content = Column(Text, default="")
    updated_at = Column(DateTime, default=utcnow)


class AnalysisRun(Base):
    __tablename__ = "analysis_run"
    id = Column(Integer, primary_key=True)
    shop_id = Column(Integer, nullable=False)
    user_id = Column(Integer, nullable=True)
    date_start = Column(Date, nullable=True)
    date_end = Column(Date, nullable=True)
    scope_json = Column(Text, default="{}")
    provider_id = Column(Integer, nullable=True)
    mode = Column(String(16), default="rule")     # llm | rule
    status = Column(String(16), default="success")
    tokens = Column(Integer, default=0)
    cost = Column(Float, default=0.0)
    duration_ms = Column(Integer, default=0)
    message = Column(Text, default="")
    fingerprint = Column(String(64), default="")
    created_at = Column(DateTime, default=utcnow)


class ActionItem(Base):
    __tablename__ = "action_item"
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("analysis_run.id"))
    dimension = Column(String(32))
    title = Column(String(256))
    detail = Column(Text, default="")
    action = Column(Text, default="")
    expected_impact = Column(Text, default="")
    priority = Column(String(16), default="P2")
    confidence = Column(Float, default=0.6)
    status = Column(String(16), default="pending")   # pending|adopted|rejected|done
    created_at = Column(DateTime, default=utcnow)


class Evidence(Base):
    __tablename__ = "evidence"
    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey("action_item.id"))
    metric_path = Column(String(256), default="")
    query_fingerprint = Column(String(64), default="")
    snapshot_json = Column(Text, default="{}")
    source_file_id = Column(Integer, nullable=True)
    source_rows = Column(Text, default="")


# ---------------------------------------------------------------- 知识库
class KbKeyword(Base):
    __tablename__ = "kb_keyword"
    id = Column(Integer, primary_key=True)
    shop_id = Column(Integer, default=0)
    term = Column(String(256))
    intent = Column(String(32), default="")
    relevance = Column(String(16), default="high")
    status = Column(String(16), default="active")   # active|watch|negative
    asin = Column(String(32), default="")
    note = Column(Text, default="")
    updated_by = Column(String(64), default="")
    updated_at = Column(DateTime, default=utcnow)


class KbBidRule(Base):
    __tablename__ = "kb_bid_rule"
    id = Column(Integer, primary_key=True)
    shop_id = Column(Integer, default=0)
    keyword = Column(String(256), default="*")
    match_type = Column(String(16), default="exact")
    placement = Column(String(32), default="all")
    base_cpc = Column(Float, default=0.8)
    min_cpc = Column(Float, default=0.2)
    max_cpc = Column(Float, default=2.5)
    step = Column(Float, default=0.1)
    note = Column(Text, default="")
    updated_by = Column(String(64), default="")
    updated_at = Column(DateTime, default=utcnow)


class KbRankTrack(Base):
    """排名追踪：按 ASIN/关键词/站点记录自然与广告排名，支撑趋势与掉落预警（P1-3）。"""
    __tablename__ = "kb_rank_track"
    id = Column(Integer, primary_key=True)
    shop_id = Column(Integer, default=0)
    asin = Column(String(32), default="")
    term = Column(String(256), default="")
    marketplace = Column(String(16), default="US")          # US|DE|UK|JP|... 站点
    rank_source = Column(String(16), default="manual")       # manual|aba|import
    track_date = Column(Date, default=date.today)
    organic_rank = Column(Integer, default=0)
    ad_rank = Column(Integer, default=0)
    page = Column(Integer, default=1)
    __table_args__ = (Index("ix_kb_rank_shop_asin_term_mp", "shop_id", "asin", "term", "marketplace"),)


class KbCompetitor(Base):
    __tablename__ = "kb_competitor"
    id = Column(Integer, primary_key=True)
    shop_id = Column(Integer, default=0)
    competitor_asin = Column(String(32), default="")
    brand = Column(String(128), default="")
    price = Column(Float, default=0.0)
    rating = Column(Float, default=0.0)
    reviews = Column(Integer, default=0)
    selling_points = Column(Text, default="")
    note = Column(Text, default="")
    updated_by = Column(String(64), default="")
    updated_at = Column(DateTime, default=utcnow)


class KbChangeLog(Base):
    __tablename__ = "kb_change_log"
    id = Column(Integer, primary_key=True)
    shop_id = Column(Integer, default=0)
    entity = Column(String(32))
    entity_id = Column(Integer, default=0)
    field = Column(String(64), default="")
    old_value = Column(Text, default="")
    new_value = Column(Text, default="")
    operator = Column(String(64), default="")
    created_at = Column(DateTime, default=utcnow)


# ---------------------------------------------------------------- 冷启动
class LaunchProject(Base):
    __tablename__ = "launch_project"
    id = Column(Integer, primary_key=True)
    shop_id = Column(Integer, default=1)
    asin = Column(String(32), default="")
    title = Column(String(256), default="")
    category = Column(String(128), default="")
    marketplace = Column(String(16), default="US")
    target_acos = Column(Float, default=35.0)
    daily_budget = Column(Float, default=60.0)
    cycle_days = Column(Integer, default=30)
    status = Column(String(16), default="draft")
    created_by = Column(String(64), default="")
    created_at = Column(DateTime, default=utcnow)


class LaunchPlanNode(Base):
    __tablename__ = "launch_plan_node"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("launch_project.id"))
    parent_id = Column(Integer, nullable=True)
    node_type = Column(String(16))       # campaign | adgroup | keyword
    name = Column(String(256), default="")
    match_type = Column(String(16), default="")
    bid = Column(Float, default=0.0)
    budget = Column(Float, default=0.0)
    note = Column(Text, default="")
    sort_order = Column(Integer, default=0)


class LaunchExport(Base):
    __tablename__ = "launch_export"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, nullable=True)
    file_type = Column(String(32), default="sp-bulk")
    file_path = Column(String(512), default="")
    row_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)
