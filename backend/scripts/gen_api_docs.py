"""从 FastAPI OpenAPI 规范生成 Markdown 接口文档（T5）。

输出：<repo>/docs/API.md
运行：python _gen_api_docs.py
"""
import json
import os
import sys
from datetime import date

os.environ.setdefault("DATABASE_URL", "sqlite:///./data/_apidoc_tmp.db")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(SCRIPT_DIR)          # backend/
sys.path.insert(0, BACKEND)

from app.main import app  # noqa: E402

SPEC = app.openapi()
SCHEMAS = SPEC.get("components", {}).get("schemas", {})
REPO = os.path.dirname(BACKEND)                # 仓库根
OUT = os.path.join(REPO, "docs", "API.md")

TAG_META = {
    "ingest": ("数据接入", "广告报表上传、字段映射预览、入库与数据版本管理。"),
    "bi": ("BI 分析", "广告投放指标的聚合查询、趋势、结构与下钻。"),
    "analysis": ("智能分析", "多模型/规则引擎运行、建议审阅、规则与模型配置管理。"),
    "inventory": ("库存健康", "库存周转、可售天数与断货风险概览。"),
    "kb": ("知识库", "关键词库、竞品库、Listing 与素材等知识的增删改查。"),
    "launch": ("新品上市", "新品上市方案与节点（里程碑）管理。"),
    "comment": ("协作评论", "建议/对象上的评论线程（协作讨论）。"),
    "notify": ("告警推送", "告警渠道配置、测试与推送记录。"),
    "admin": ("系统管理", "登录、用户管理与权限。"),
    "default": ("系统", "健康检查等基础接口。"),
}
TAG_ORDER = ["ingest", "bi", "analysis", "inventory", "kb", "launch",
             "comment", "notify", "admin", "default"]

# 端点中文摘要（键为 (METHOD, path)）
SUMMARY_ZH = {
    ("POST", "/api/ingest/preview"): "上传广告报表并预览（解析表头、字段映射、逐行校验）",
    ("POST", "/api/ingest/commit"): "确认映射并入库（生成数据版本，支持覆盖/追加）",
    ("GET", "/api/ingest/report-types"): "支持的报表类型清单",
    ("GET", "/api/ingest/versions"): "已入库的数据版本列表",
    ("POST", "/api/ingest/rollback/{version_id}"): "回滚到指定数据版本",
    ("GET", "/api/ingest/jobs"): "导入任务记录",
    ("GET", "/api/ingest/issues"): "数据质量问题清单",
    ("GET", "/api/bi/metrics"): "统一指标口径（名称 / 单位 / 公式说明）",
    ("GET", "/api/bi/shops"): "当前用户可访问的店铺（含站点 / 币种 / 时区）",
    ("GET", "/api/bi/range"): "可用数据日期范围",
    ("GET", "/api/bi/campaigns"): "广告活动清单（用于筛选器）",
    ("GET", "/api/bi/query"): "指标聚合查询（按维度分组 + 筛选 + 排序 + 分页）",
    ("GET", "/api/bi/trend"): "指标按日趋势",
    ("GET", "/api/bi/overview"): "概览与环比（当期 vs 上期）",
    ("GET", "/api/bi/drill"): "层级下钻（活动 → 广告组 → 关键词）",
    ("GET", "/api/analysis/providers"): "模型 / 运行配置清单",
    ("POST", "/api/analysis/providers"): "新增或更新模型配置",
    ("DELETE", "/api/analysis/providers/{pid}"): "删除模型配置",
    ("POST", "/api/analysis/providers/{pid}/test"): "测试模型连通性",
    ("GET", "/api/analysis/dimensions"): "12 个分析维度定义",
    ("GET", "/api/analysis/dsl/meta"): "DSL 规则构建器元数据（指标 / 运算符 / 作用域 / 维度）",
    ("GET", "/api/analysis/dsl/validate"): "校验 DSL 规则文本并返回解析结果",
    ("GET", "/api/analysis/rules"): "规则清单",
    ("POST", "/api/analysis/rules"): "新建规则",
    ("PUT", "/api/analysis/rules/{rid}"): "更新规则（启用 / 条件 / 优先级 / 模板 / DSL）",
    ("DELETE", "/api/analysis/rules/{rid}"): "删除规则",
    ("POST", "/api/analysis/run"): "运行分析（规则引擎 / 单模型 LLM / 多模型对比）",
    ("GET", "/api/analysis/runs"): "历史运行记录",
    ("GET", "/api/analysis/runs/{rid}"): "单次运行详情（含建议项）",
    ("GET", "/api/analysis/compare"): "重取多模型对比结果",
    ("GET", "/api/analysis/retro"): "复盘数据",
    ("GET", "/api/analysis/prompt"): "获取提示词模板",
    ("PUT", "/api/analysis/prompt"): "保存提示词模板",
    ("POST", "/api/analysis/items/{iid}/status"): "更新建议项状态（采纳 / 忽略等）",
    ("POST", "/api/analysis/items/{iid}/execute"): "执行建议项动作",
    ("GET", "/api/analysis/items/{iid}/execution"): "查询建议项执行结果",
    ("GET", "/api/inventory"): "库存健康概览（可售天数、断货风险）",
    ("GET", "/api/kb/{entity}"): "列出知识库实体（关键词 / 竞品 / 排名等）",
    ("POST", "/api/kb/{entity}"): "新增知识库记录",
    ("PUT", "/api/kb/{entity}/{eid}"): "更新知识库记录",
    ("DELETE", "/api/kb/{entity}/{eid}"): "删除知识库记录",
    ("GET", "/api/kb/{entity}/export"): "导出知识库为 CSV",
    ("POST", "/api/kb/import"): "批量导入记录",
    ("GET", "/api/kb/aba/terms"): "ABA 搜索词热度数据",
    ("GET", "/api/kb/rank/trend"): "关键词排名趋势",
    ("POST", "/api/kb/rank/from-aba"): "从 ABA 数据生成排名记录",
    ("GET", "/api/kb/changes/log"): "知识库变更日志",
    ("POST", "/api/launch/generate"): "生成新品上市方案（含节点）",
    ("GET", "/api/launch/projects"): "上市方案清单",
    ("GET", "/api/launch/projects/{pid}"): "方案详情（含节点）",
    ("GET", "/api/launch/projects/{pid}/export"): "导出方案（CSV / JSON）",
    ("POST", "/api/launch/nodes"): "新增节点",
    ("PUT", "/api/launch/nodes/{nid}"): "更新节点",
    ("DELETE", "/api/launch/nodes/{nid}"): "删除节点",
    ("GET", "/api/comment"): "列出评论（按对象维度）",
    ("POST", "/api/comment"): "发表评论",
    ("PUT", "/api/comment/{cid}"): "编辑评论（仅本人）",
    ("DELETE", "/api/comment/{cid}"): "删除评论（仅本人）",
    ("GET", "/api/notify/channels"): "告警渠道清单",
    ("POST", "/api/notify/channels"): "新增渠道",
    ("PUT", "/api/notify/channels/{cid}"): "更新渠道",
    ("DELETE", "/api/notify/channels/{cid}"): "删除渠道",
    ("POST", "/api/notify/test"): "发送测试消息",
    ("GET", "/api/notify/logs"): "推送记录",
    ("POST", "/api/admin/login"): "用户名密码登录",
    ("GET", "/api/admin/users"): "用户清单",
    ("POST", "/api/admin/users"): "新增 / 更新用户",
    ("DELETE", "/api/admin/users/{uid}"): "删除用户",
    ("GET", "/api/admin/shops"): "店铺清单",
    ("POST", "/api/admin/shops"): "新增店铺",
    ("GET", "/api/admin/usage"): "用量统计",
    ("GET", "/api/admin/audit"): "操作审计日志",
    ("GET", "/api/health"): "健康检查",
}


# 常用参数中文说明（按参数名复用；未命中时回退到接口自身的 description）
PARAM_ZH = {
    "X-Username": "操作者用户名（缺省 `admin`）",
    "shop_id": "店铺 ID，可重复传多个；缺省为当前用户可访问的全部店铺",
    "marketplace": "站点代码（如 `US`）",
    "start": "起始日期，格式 `YYYY-MM-DD`（缺省取可用范围起点）",
    "end": "结束日期，格式 `YYYY-MM-DD`（缺省取可用范围终点）",
    "group_by": "聚合维度，如 `campaign` / `adgroup` / `keyword` / `ad_format` / `placement` / `targeting`",
    "filters": "过滤条件，JSON 字符串（如 `{\"campaign_ids\":[\"C1\"]}`）",
    "sort_by": "排序字段",
    "sort_dir": "排序方向：`asc` / `desc`",
    "page": "页码，从 1 开始",
    "size": "每页条数",
    "days": "统计天数（用于环比 / 用量窗口）",
    "campaign_id": "广告活动 ID（下钻起点）",
    "adgroup_id": "广告组 ID（进一步下钻到关键词）",
    "limit": "返回条数上限",
    "offset": "偏移量（分页）",
    "entity": "知识库实体类型，如 `keyword` / `competitor` / `rank` / `listing`",
    "eid": "记录 ID",
    "rid": "运行记录 ID / 规则 ID",
    "pid": "模型配置 ID / 方案 ID",
    "cid": "渠道 ID / 评论 ID",
    "nid": "节点 ID",
    "uid": "用户 ID",
    "iid": "建议项 ID",
    "version_id": "数据版本 ID",
    "text": "待校验的 DSL 规则文本",
    "code": "代码 / 标识（如规则 code、提示词 code）",
    "group": "多模型对比分组 ID",
    "q": "搜索关键字",
    "status": "状态过滤",
}


def param_desc(name, fallback):
    return PARAM_ZH.get(name) or (fallback or "-").strip() or "-"


# 关键接口的响应结构（这些路由返回未类型化 dict，OpenAPI 无法推导）
RESPONSE_ZH = {
    ("GET", "/api/health"): '{"ok": true, "service": "amz-ad-workbench", "version": "0.1.0"}',
    ("GET", "/api/bi/metrics"): '{"items": [{"code", "name_zh", "unit", "desc"} ...]}',
    ("GET", "/api/bi/shops"): '{"items": [{"id", "name", "marketplace", "currency", "timezone"} ...]}',
    ("GET", "/api/bi/range"): '{"start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "shop_ids": [1, 2]}',
    ("GET", "/api/bi/campaigns"): '{"items": [{"id", "name"} ...]}',
    ("GET", "/api/bi/query"): '{"rows": [{<group_by 维度列>, <指标字段...>}], "total": 123, '
                              '"summary": {<指标>}, "total_sales": 0.0, "group_by": "campaign", "shop_ids": [1]}',
    ("GET", "/api/bi/trend"): '{"points": [{"date", "spend", "sales", "acos", "orders"} ...], "summary": {<指标>}}',
    ("GET", "/api/bi/overview"): '{"period": ["起", "止"], "current": {<指标>}, "previous": {<指标>}, '
                                 '"delta": {<指标>}, "shop_ids": [1]}',
    ("GET", "/api/bi/drill"): '{"level": "campaign | adgroup | keyword", "rows": [{...}]}',
    ("GET", "/api/inventory"): '{"items": [{"shop_id", "asin", "sku", "date", "qty", "inbound", '
                               '"days_of_cover", "advertised", "low_stock"} ...], '
                               '"summary": {"asin_count", "low_count", "advertised_low", "threshold"}}',
    ("POST", "/api/analysis/run"): '// 规则/单模型：\n'
                                   '{"mode": "rule | llm", "items": [<建议项>], "run_id": 12}\n'
                                   '// 多模型对比（provider_ids 非空）：\n'
                                   '{"mode": "compare", "run_id": 12, "results": [{"provider": {...}, "items": [...]}], '
                                   '"summary": {"shared_dims": [...], "unique_dims": {...}, "dim_matrix": {...}}}',
    ("GET", "/api/analysis/compare"): '{"mode": "compare", "results": [{"provider": {...}, "items": [...]}], "summary": {...}}',
    ("GET", "/api/analysis/runs"): '{"items": [{"id", "shop_id", "mode", "provider", "created_at", "item_count"} ...]}',
    ("GET", "/api/analysis/runs/{rid}"): '{"run": {...}, "items": [<建议项>]}',
    ("GET", "/api/analysis/rules"): '{"items": [{"id", "code", "name_zh", "dimension", "enabled", "priority", "dsl_text"} ...]}',
    ("GET", "/api/analysis/dimensions"): '{"items": [{"code", "name_zh"} ...]}',
    ("GET", "/api/analysis/providers"): '{"items": [{"id", "name", "kind", "endpoint", "model", "enabled"} ...]}',
    ("GET", "/api/analysis/dsl/meta"): '{"metrics": [...], "ops": [...], "scopes": [...], "dimensions": [...], "severities": [...]}',
    ("GET", "/api/analysis/dsl/validate"): '{"ok": true, "errors": [], "parsed": {<解析结果>}}',
    ("POST", "/api/admin/login"): '{"ok": true, "user": {"id", "username", "full_name", "role", "shop_ids", '
                                  '"quota_tokens", "quota_cost"}}',
    ("GET", "/api/admin/users"): '{"items": [{"id", "username", "full_name", "role", "status", "shop_ids", '
                                 '"quota_tokens", "used_tokens", "used_cost", "created_at"} ...]}',
    ("GET", "/api/admin/shops"): '{"items": [{"id", "name", "marketplace", "currency", "timezone"} ...]}',
    ("GET", "/api/comment"): '{"items": [{"id", "object_type", "object_id", "content", "author", "created_at"} ...]}',
    ("GET", "/api/notify/channels"): '{"items": [{"id", "name", "chan_type", "url", "enabled"} ...]}',
    ("GET", "/api/notify/logs"): '{"items": [{"id", "channel", "status", "message", "created_at"} ...]}',
    ("GET", "/api/launch/projects"): '{"items": [{"id", "asin", "title", "status", "created_at"} ...]}',
    ("GET", "/api/kb/{entity}"): '{"items": [{...}], "total": 123}',
    ("POST", "/api/ingest/preview"): '{"tmp_path": "...", "columns": [...], "mapping": {...}, "sample": [...], "issues": [...]}',
}


def perm_of(path):
    if path.startswith("/api/admin/") and path != "/api/admin/login":
        return "管理员"
    if path == "/api/admin/login" or path == "/api/health":
        return "公开"
    return "登录用户"


def zh_summary(method, path, op):
    return SUMMARY_ZH.get((method, path)) or op.get("summary", "")


def ref_name(ref):
    return ref.split("/")[-1] if ref else ""


def resolve(schema, depth=0):
    if not isinstance(schema, dict):
        return {}
    if depth > 6:
        return schema
    if "$ref" in schema:
        return resolve(SCHEMAS.get(ref_name(schema["$ref"]), {}), depth + 1)
    return schema


def type_of(schema):
    schema = resolve(schema)
    if not schema:
        return "-"
    if "anyOf" in schema:
        parts = []
        for s in schema["anyOf"]:
            if s.get("type") == "null":
                continue
            parts.append(type_of(s))
        t = " | ".join(dict.fromkeys(p for p in parts if p != "-")) or "any"
        return t + "?" if any(s.get("type") == "null" for s in schema["anyOf"]) else t
    if "allOf" in schema:
        return " & ".join(type_of(s) for s in schema["allOf"])
    t = schema.get("type", "object" if "properties" in schema else "any")
    if t == "array":
        return f"array<{type_of(schema.get('items', {}))}>"
    if t == "object" and "additionalProperties" in schema:
        ap = schema["additionalProperties"]
        if isinstance(ap, bool):
            return "map<any>" if ap else "object"
        return f"map<{type_of(ap)}>"
    if "enum" in schema:
        return t + " (枚举)"
    return t


def fmt_props(schema, indent=""):
    """把对象 schema 展开为参数/字段表格行。"""
    schema = resolve(schema)
    props = schema.get("properties")
    if not props:
        return []
    required = set(schema.get("required", []))
    rows = []
    for name, ps in props.items():
        ps2 = resolve(ps)
        desc = (ps2.get("description") or "").replace("\n", " ").strip()
        if "enum" in ps2:
            desc += (" ；可选：" if desc else "可选：") + ", ".join(f"`{e}`" for e in ps2["enum"])
        if "default" in ps2 and ps2["default"] is not None:
            desc += ("；" if desc else "") + f"默认 `{ps2['default']}`"
        rows.append((name, type_of(ps), "是" if name in required else "否", desc or "-"))
    return rows


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


def iter_ops():
    for path, methods in SPEC.get("paths", {}).items():
        if not path.startswith("/api/"):      # 跳过 SPA 兜底路由
            continue
        for method, op in methods.items():
            if method.lower() not in ("get", "post", "put", "delete", "patch"):
                continue
            yield path, method.upper(), op


lines = []
A = lines.append
A("# AI 广告分析工作台 · API 接口文档")
A("")
A(f"> 版本 `{SPEC['info'].get('version', '0.1.0')}` · 依据 FastAPI OpenAPI 自动生成 · 生成日期 {date.today():%Y-%m-%d}")
A("")
A("## 1. 通用约定")
A("")
A("- **Base URL**：`http://<host>:8000`（本地开发默认 `http://127.0.0.1:8000`）")
A("- **数据格式**：请求与响应均为 `application/json`；文件上传接口为 `multipart/form-data`。")
A("- **在线文档**：Swagger UI `/docs`，ReDoc `/redoc`，原始规范 `/openapi.json`。")
A("- **分页/筛选**：以各接口的查询参数为准（见第 4 节）。")
A("")
A("## 2. 鉴权")
A("")
A("采用轻量请求头鉴权（MVP 方案）：")
A("")
A("- 所有需要身份的接口从请求头 **`X-Username`** 读取操作者；**缺省值为 `admin`**。")
A("- 依据用户名查找 `User`；用户不存在时回退到系统首个用户（便于本地免配置调试）。")
A("- 权限模型：`admin` 可访问全部店铺；`operator` 仅能访问 `allowed_shop_ids` 中授权的店铺，越权返回 `403`。")
A("- 密码存储：`sha256(\"amz::\" + 明文)`（见 `app/auth.py`）。")
A("- 生产环境应替换为 JWT/OAuth。")
A("")
A("> 完整错误码与鉴权规则见 [`ERROR_CODES.md`](./ERROR_CODES.md)。")
A("")
A("## 3. 接口一览")
A("")
overview = []
for tag in TAG_ORDER:
    rows = [(m, p, perm_of(p), zh_summary(m, p, op) or "—")
            for p, m, op in iter_ops() if tag in (op.get("tags") or ["default"])]
    if not rows:
        continue
    name = TAG_META.get(tag, (tag, ""))[0]
    A(f"### {name}（`{tag}`）")
    A("")
    A(table(["方法", "路径", "权限", "说明"], sorted(rows, key=lambda r: (r[1], r[0]))))
    A("")

A("## 4. 接口详情")
A("")
for tag in TAG_ORDER:
    ops = [(p, m, op) for p, m, op in iter_ops() if tag in (op.get("tags") or ["default"])]
    if not ops:
        continue
    name, desc = TAG_META.get(tag, (tag, ""))
    A(f"### {name}（`{tag}`）")
    A("")
    if desc:
        A(desc)
        A("")
    for path, method, op in sorted(ops, key=lambda x: (x[0], x[1])):
        A(f"#### `{method}` {path}")
        A("")
        title = zh_summary(method, path, op)
        if title:
            A(f"**{title}**")
            A("")
        A(f"- 权限：**{perm_of(path)}**")
        desc = (op.get("description") or "").strip()
        if desc and desc != title:
            A(f"- 补充：{desc}")
        A("")
        # 参数
        params = op.get("parameters", [])
        if params:
            rows = []
            for p in params:
                ps = resolve(p.get("schema", {}))
                desc = param_desc(p["name"], p.get("description"))
                extra = ""
                if "enum" in ps:
                    extra += " 可选：" + ", ".join(f"`{e}`" for e in ps["enum"])
                if ("default" in ps and ps["default"] not in (None, "")
                        and "默认" not in desc and "缺省" not in desc):
                    extra += f" 默认 `{ps['default']}`"
                rows.append((f"`{p['name']}`", p["in"], type_of(ps),
                             "是" if p.get("required") else "否", desc + extra))
            A("**参数**")
            A("")
            A(table(["名称", "位置", "类型", "必填", "说明"], rows))
            A("")
        # 请求体
        rb = op.get("requestBody", {})
        if rb:
            content = rb.get("content", {})
            for ctype, cs in content.items():
                schema = cs.get("schema", {})
                rows = fmt_props(schema)
                A(f"**请求体**（`{ctype}`）")
                A("")
                if rows:
                    A(table(["字段", "类型", "必填", "说明"], rows))
                else:
                    A(f"类型：`{type_of(schema)}`")
                A("")
        # 响应
        resp = op.get("responses", {})
        codes = ", ".join(sorted(c for c in resp if str(c).startswith("2")))
        A(f"**成功响应**：`{codes or '200'}`")
        A("")
        hint = RESPONSE_ZH.get((method, path))
        if hint:
            A("返回结构：")
            A("")
            A("```jsonc" if hint.lstrip().startswith("//") else "```json")
            A(hint)
            A("```")
            A("")
        else:
            ok = None
            for c in ("200", "201", "202"):
                if c in resp:
                    ok = resp[c]
                    break
            if ok:
                rows = fmt_props(ok.get("content", {}).get("application/json", {}).get("schema", {}))
                if rows:
                    A(table(["字段", "类型", "必填", "说明"], rows))
                    A("")
                else:
                    s = ok.get("content", {}).get("application/json", {}).get("schema", {})
                    if s:
                        A(f"返回 `{type_of(s)}`。")
                        A("")
        A("**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · "
          "`404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败")
        A("")
A("---")
A("")
A("_本文档由 `backend/scripts/gen_api_docs.py` 依据 OpenAPI 规范生成；接口变更后请重新生成以保持同步。_")

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print("WROTE", OUT, "lines=", len(lines))
