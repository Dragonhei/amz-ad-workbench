"""报表解析引擎：编码探测 → 定位表头 → 类型识别 → 字段映射 → 值清洗 → 行级校验。"""
import csv
import io
import os
import re
import difflib
from datetime import datetime, timedelta, date

EXCEL_EPOCH = datetime(1899, 12, 30)

# ---------------------------------------------------------------- 报表类型定义
REPORT_TYPES = {
    "SP": "商品推广广告报表",
    "SB": "品牌推广广告报表",
    "SD": "展示型推广广告报表",
    "ST": "搜索词报告",
    "BR": "品牌指标报告",
    "ABA": "ABA 搜索词报告",
    "BIZ": "业务报告（TACOS 分母 / 库存）",
    "INV": "库存报表（可售 / 在途 / 可售天数）",
}

# canonical 字段 → 说明
CANONICAL_FIELDS = {
    "SP": ["date", "campaign_id", "campaign_name", "adgroup_id", "adgroup_name",
           "keyword", "match_type", "targeting", "impressions", "clicks", "spend",
           "orders", "units", "sales"],
    "ST": ["date", "campaign_id", "campaign_name", "adgroup_id", "adgroup_name",
           "search_term", "match_type", "impressions", "clicks", "spend", "orders", "sales"],
    "BR": ["date", "asin", "brand_search_volume", "new_to_brand_orders",
           "new_to_brand_pct", "repeat_purchase_pct"],
    "ABA": ["week_start", "search_term", "search_rank", "top3_click_share", "top3_conv_share"],
    "BIZ": ["date", "asin", "sessions", "page_views", "units", "orders", "total_sales", "inventory"],
    "INV": ["date", "asin", "sku", "qty", "inbound", "daily_sales", "days_of_cover"],
}
# SB/SD 复用 SP 的基础列，并补充品牌/展示广告特有维度
_SB_SD_EXTRA = ["landing_page_id", "creative_id", "headline", "audience_id", "placement", "associated_asin"]
CANONICAL_FIELDS["SB"] = CANONICAL_FIELDS["SP"] + _SB_SD_EXTRA
CANONICAL_FIELDS["SD"] = CANONICAL_FIELDS["SP"] + _SB_SD_EXTRA

REQUIRED_FIELDS = {
    "SP": ["date", "impressions", "clicks", "spend"],
    "SB": ["date", "impressions", "clicks", "spend"],
    "SD": ["date", "impressions", "clicks", "spend"],
    "ST": ["date", "search_term", "clicks", "spend"],
    "BR": ["date", "brand_search_volume"],
    "ABA": ["search_term", "search_rank"],
    "BIZ": ["date", "asin", "sessions"],
    "INV": ["date", "asin", "qty"],
}

# 别名表：canonical → 可能出现的表头（英文 / 中文 / 变体）
ALIASES = {
    "date": ["date", "start date", "reporting date", "day", "日期", "统计日期", "时间"],
    "campaign_id": ["campaign id", "campaignid", "广告活动id"],
    "campaign_name": ["campaign name", "campaign", "campaigns", "广告活动名称", "广告活动", "广告系列"],
    "adgroup_id": ["ad group id", "adgroup id", "广告组id"],
    "adgroup_name": ["ad group name", "adgroup name", "ad group", "广告组名称", "广告组"],
    "keyword": ["keyword", "keywords", "targeting", "关键词", "投放"],
    "match_type": ["match type", "matching", "匹配方式", "匹配类型"],
    "targeting": ["targeting", "targeting expression", "投放", "定向"],
    "search_term": ["customer search term", "search term", "search terms", "searchterm",
                    "customer search terms", "搜索词", "客户搜索词", "搜索词报告"],
    "impressions": ["impressions", "impr", "impression", "曝光量", "曝光", "展示量"],
    "clicks": ["clicks", "click", "点击量", "点击", "点击次数"],
    "spend": ["spend", "cost", "spend(usd)", "cost of sales", "花费", "广告花费", "支出"],
    "orders": ["orders", "# orders", "total orders", "订单量", "订单数", "订单", "销量(广告)"],
    "units": ["units", "units sold", "total units", "销量", "销售数量"],
    "sales": ["sales", "total sales", "attributed sales", "sales(usd)", "广告销售额", "销售额",
              "attributed sales value", "total attributed sales"],
    "asin": ["asin", "child asin", "asin(s)", "商品asin"],
    "brand_search_volume": ["brand search volume", "brand searches", "品牌搜索量", "品牌搜索次数"],
    "new_to_brand_orders": ["new-to-brand orders", "new to brand orders", "ntb orders", "新客订单"],
    "new_to_brand_pct": ["new-to-brand %", "new to brand %", "ntb %", "新客占比"],
    "repeat_purchase_pct": ["repeat purchase %", "repeat purchases", "复购率"],
    "week_start": ["week", "week ending", "week start", "reporting week", "周", "周起始"],
    "search_rank": ["search frequency rank", "abs search frequency rank", "search rank",
                    "rank", "搜索频率排名", "排名"],
    "top3_click_share": ["#1-#3 click share", "top3 click share", "click share",
                         "前三点击份额", "点击份额"],
    "top3_conv_share": ["#1-#3 conversion share", "top3 conversion share", "conversion share",
                        "前三转化份额", "转化份额"],
    "sessions": ["sessions", "session", "会话量", "会话", "浏览次数"],
    "page_views": ["page views", "pageviews", "页面浏览量"],
    "total_sales": ["ordered product sales", "total product sales", "total sales", "总销售额"],
    "inventory": ["inventory", "available inventory", "库存", "可用库存"],
    # 库存报表（INV）专用列别名
    "sku": ["sku", "merchant sku", "seller sku", "商品编码", "货号"],
    "qty": ["qty", "quantity", "available", "available units", "sellable", "sellable units",
            "in stock", "units available", "可售库存", "可用库存量"],
    "inbound": ["inbound", "inbound units", "in-transit", "in transit", "shipped to amazon",
                "receipts", "inbound shipped", "在途", "在途库存", "已发货"],
    "daily_sales": ["units sold", "units ordered", "daily sales", "sales units", "日销量", "日均销量"],
    "days_of_cover": ["days of cover", "cover days", "weeks of cover", "days cover",
                      "可售天数", "可覆盖天数"],
    # SB/SD 专用列别名
    "landing_page_id": ["landing page", "landing page id", "landing page url", "落地页", "落地页id"],
    "creative_id": ["creative", "creative id", "creative name", "创意", "创意id"],
    "headline": ["headline", "标题", "广告标题"],
    "audience_id": ["audience", "audience id", "matched audience", "受众", "受众id"],
    "placement": ["placement", "placement type", "page type", "投放位置", "页面类型", "版位"],
    "associated_asin": ["advertised asin", "advertised asin(s)", "promoted asin", "推广asin",
                        "广告asin", "商品定向asin"],
}

# ID 类字段不参与模糊匹配，避免抢走同名的 Name 列（如 Campaign Name）
NO_FUZZY = {"campaign_id", "adgroup_id", "keyword_id"}

NUMERIC_FIELDS = {"impressions", "clicks", "spend", "orders", "units", "sales",
                  "brand_search_volume", "new_to_brand_orders", "new_to_brand_pct",
                  "repeat_purchase_pct", "search_rank", "top3_click_share", "top3_conv_share",
                  "sessions", "page_views", "total_sales", "inventory",
                  "qty", "inbound", "daily_sales", "days_of_cover"}
INT_FIELDS = {"impressions", "clicks", "orders", "units", "brand_search_volume",
              "new_to_brand_orders", "search_rank", "sessions", "page_views", "inventory",
              "qty", "inbound"}


# ---------------------------------------------------------------- 读取文件
def _decode(raw: bytes):
    """编码探测：UTF-8(BOM) → GBK → UTF-16 → Latin-1 兜底。"""
    for enc in ("utf-8-sig", "utf-8", "gbk", "utf-16", "latin-1"):
        try:
            return raw.decode(enc), enc
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace"), "utf-8(replace)"


def _open_xlsx(path):
    from openpyxl import load_workbook
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = []
    for r in ws.iter_rows(values_only=True):
        if r is None:
            continue
        rows.append(["" if c is None else str(c) for c in r])
    wb.close()
    return rows


def read_table(path: str):
    """返回 (rows, encoding, issues)。自动跳过前导说明行。"""
    issues = []
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xlsm", ".xls"):
        rows = _open_xlsx(path)
        encoding = "xlsx"
    else:
        with open(path, "rb") as f:
            raw = f.read()
        text, encoding = _decode(raw)
        sample = text[:8192]
        delimiter = "\t" if sample.count("\t") > sample.count(",") else ","
        rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    if not rows:
        return [], encoding, [{"row_no": 0, "severity": "blocking", "column_name": "",
                               "raw_value": "", "message": "文件为空或无法读取"}]

    header_idx = _find_header_row(rows)
    if header_idx > 0:
        issues.append({"row_no": 1, "severity": "warning", "column_name": "",
                       "raw_value": "",
                       "message": f"已自动跳过前 {header_idx} 行说明/空行"})
    headers = [h.strip().strip('"').strip() for h in rows[header_idx]]
    headers = [h if h else f"col_{i}" for i, h in enumerate(headers)]
    body = []
    for i, r in enumerate(rows[header_idx + 1:], start=header_idx + 2):
        if not any((c or "").strip() for c in r):
            continue
        body.append((i, r))
    return headers, body, encoding, issues, header_idx


def _find_header_row(rows, limit=25):
    """表头行 = 已知别名命中数最多的行。"""
    all_alias = set()
    for v in ALIASES.values():
        all_alias.update(v)
    best_idx, best_score = 0, -1
    for idx, r in enumerate(rows[:limit]):
        if not r:
            continue
        score = sum(1 for c in r if str(c).strip().lower() in all_alias)
        nonempty = sum(1 for c in r if str(c).strip())
        if score >= 2 and score > best_score:
            best_idx, best_score = idx, score
        elif best_score < 0 and nonempty >= 3:
            best_idx = idx
    return best_idx


# ---------------------------------------------------------------- 类型识别
def detect_type(headers, filename=""):
    """基于表头指纹 + 文件名打分，返回 (type, confidence, 各类型得分)。"""
    hl = [h.strip().lower() for h in headers]
    hset = set(hl)
    fn = (filename or "").lower()
    scores = {t: 0 for t in REPORT_TYPES}

    def has(*words):
        return any(any(w in h for h in hl) for w in words)

    if has("customer search term", "搜索词"):
        scores["ST"] += 12                      # 决定性特征：搜索词列
    elif has("search term", "searchterm"):
        scores["ST"] += 8
    if has("asin", "child asin") and has("sessions"):
        scores["BIZ"] += 6
    if has("brand search volume", "new-to-brand", "品牌搜索量"):
        scores["BR"] += 12
    if has("search frequency rank", "click share", "conversion share", "搜索频率排名"):
        scores["ABA"] += 12
    if has("impressions", "clicks", "spend", "曝光", "点击", "花费"):
        scores["SP"] += 3
        scores["SB"] += 1
        scores["SD"] += 1
    if has("campaign name", "ad group", "广告活动", "广告组"):
        scores["SP"] += 2
        scores["SB"] += 1
    if has("portfolio", "广告组合"):
        scores["SP"] += 1
    # SB/SD 指纹：品牌 / 展示广告特有列（决定性权重，确保优先于 SP）
    if has("sponsored brands") or has("landing page", "creative", "headline"):
        scores["SB"] += 8
    if has("sponsored display") or has("advertised asin", "page type",
                                        "matched audience", "matched target"):
        scores["SD"] += 8

    # 库存报表（INV）：含在途 / 可售天数，且不含广告 / 业务曝光指标
    if has("inbound", "in-transit", "shipped to amazon", "receipts", "在途", "已发货"):
        scores["INV"] += 10
    elif has("days of cover", "cover days", "weeks of cover", "可售天数", "可覆盖天数"):
        scores["INV"] += 10
    elif has("asin", "child asin") and (
            has("qty", "quantity", "available", "sellable", "in stock", "可售库存")
            or has("sku", "merchant sku")) and not has("impressions", "clicks", "spend",
                                                       "sessions", "page views", "ordered product sales"):
        scores["INV"] += 5

    for key, t in (("sp_", "SP"), ("sb_", "SB"), ("sd_", "SD"),
                   ("search_term", "ST"), ("searchterm", "ST"), ("search term", "ST"),
                   ("brand", "BR"), ("aba", "ABA"),
                   ("business", "BIZ"), ("businessreport", "BIZ"),
                   ("inventory", "INV"), ("inv_", "INV")):
        if key in fn:
            scores[t] += 3

    best = max(scores, key=lambda k: scores[k])
    total = sum(v for v in scores.values() if v > 0) or 1
    conf = round(scores[best] / total, 2) if scores[best] > 0 else 0.0
    if scores[best] < 3:
        return None, 0.0, scores
    return best, conf, scores


# ---------------------------------------------------------------- 字段映射
def build_mapping(headers, report_type, custom=None):
    """返回 {canonical: raw_header}；custom 为用户覆盖 {canonical: raw_header}。"""
    mapping = {}
    used = set()
    lowered = {h: h.strip().lower() for h in headers}
    if custom:
        for canon, raw in custom.items():
            if raw in headers:
                mapping[canon] = raw
                used.add(raw)
    for canon in CANONICAL_FIELDS.get(report_type, []):
        if canon in mapping:
            continue
        aliases = ALIASES.get(canon, [])
        hit = None
        for h in headers:                                  # 1) 精确命中
            if h in used:
                continue
            if lowered[h] in aliases:
                hit = h
                break
        if not hit:                                        # 2) 包含命中
            for h in headers:
                if h in used:
                    continue
                if any(a in lowered[h] or lowered[h] in a for a in aliases if len(a) > 3):
                    hit = h
                    break
        if not hit and canon not in NO_FUZZY:               # 3) 模糊匹配
            cand = difflib.get_close_matches(canon.replace("_", " "),
                                             [lowered[h] for h in headers], n=1, cutoff=0.82)
            if cand:
                matched = [h for h in headers if lowered[h] == cand[0] and h not in used]
                hit = matched[0] if matched else None
        if hit:
            mapping[canon] = hit
            used.add(hit)
    return mapping


# ---------------------------------------------------------------- 值清洗
def clean_number(v):
    if v is None:
        return 0.0
    s = str(v).strip().replace("\u00a0", "")
    if s == "" or s.lower() in ("-", "--", "n/a", "na", "null", "none"):
        return 0.0
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg, s = True, s[1:-1]
    s = s.replace("$", "").replace("USD", "").replace("¥", "").replace(",", "").replace("%", "").strip()
    if s.startswith("-"):
        neg, s = True, s[1:]
    try:
        val = float(s)
    except ValueError:
        m = re.search(r"-?\d+(\.\d+)?", s)
        if not m:
            return 0.0
        val = float(m.group(0))
    return -val if neg else val


DATE_FORMATS = ["%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%m/%d/%y", "%d/%m/%Y",
                "%Y-%m-%d %H:%M:%S", "%Y年%m月%d日", "%b %d, %Y", "%d-%m-%Y"]


def clean_date(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if v is None or str(v).strip() == "":
        return None
    s = str(v).strip().replace('"', "")
    for f in DATE_FORMATS:
        try:
            return datetime.strptime(s, f).date()
        except ValueError:
            continue
    try:                                    # Excel 序列号
        num = float(s)
        if 20000 < num < 80000:
            return (EXCEL_EPOCH + timedelta(days=num)).date()
    except ValueError:
        pass
    m = re.match(r"(\d{4})[-/]?(\d{1,2})[-/]?(\d{1,2})", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------- 行解析
def parse_rows(body, headers, mapping, report_type, max_issues=200):
    """返回 (records, issues, stats)。行级异常不阻断整批。"""
    idx = {h: i for i, h in enumerate(headers)}
    records, issues = [], []
    required = REQUIRED_FIELDS.get(report_type, [])
    missing_req = [f for f in required if f not in mapping]
    if missing_req:
        issues.append({"row_no": 0, "severity": "blocking", "column_name": ",".join(missing_req),
                       "raw_value": "", "message": f"缺少必填字段映射：{missing_req}，请手工指定列"})
        return records, issues, {"row_total": len(body), "row_ok": 0, "row_err": len(body)}

    seen = set()
    for lineno, row in body:
        def get(canon):
            raw_h = mapping.get(canon)
            if raw_h is None:
                return ""
            i = idx.get(raw_h)
            return row[i] if i is not None and i < len(row) else ""

        rec = {"__row__": lineno}
        bad = False
        for canon in CANONICAL_FIELDS.get(report_type, []):
            raw = get(canon)
            if canon in ("date", "week_start"):
                d = clean_date(raw)
                if d is None:
                    if canon == "date":
                        bad = True
                        if len(issues) < max_issues:
                            issues.append({"row_no": lineno, "severity": "warning", "column_name": canon,
                                           "raw_value": str(raw),
                                           "message": "日期无法解析，该行已跳过"})
                    continue
                rec[canon] = d
            elif canon in NUMERIC_FIELDS:
                val = clean_number(raw)
                if val < 0 and canon in ("spend", "impressions", "clicks", "orders"):
                    if len(issues) < max_issues:
                        issues.append({"row_no": lineno, "severity": "warning", "column_name": canon,
                                       "raw_value": str(raw), "message": "出现负数，已按 0 处理"})
                    val = 0.0
                rec[canon] = int(val) if canon in INT_FIELDS else round(val, 4)
            else:
                rec[canon] = str(raw).strip()
        if bad:
            continue
        if "date" in rec:
            key = (rec.get("date"), rec.get("campaign_name", ""), rec.get("adgroup_name", ""),
                   rec.get("keyword", "") or rec.get("search_term", "") or rec.get("asin", ""))
            if key in seen:
                continue
            seen.add(key)
        records.append(rec)
    stats = {"row_total": len(body), "row_ok": len(records), "row_err": len(body) - len(records)}
    return records, issues, stats
