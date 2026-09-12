# AI 广告分析工作台 · API 接口文档

> 版本 `0.1.0` · 依据 FastAPI OpenAPI 自动生成 · 生成日期 2026-09-12

## 1. 通用约定

- **Base URL**：`http://<host>:8000`（本地开发默认 `http://127.0.0.1:8000`）
- **数据格式**：请求与响应均为 `application/json`；文件上传接口为 `multipart/form-data`。
- **在线文档**：Swagger UI `/docs`，ReDoc `/redoc`，原始规范 `/openapi.json`。
- **分页/筛选**：以各接口的查询参数为准（见第 4 节）。

## 2. 鉴权

采用轻量请求头鉴权（MVP 方案）：

- 所有需要身份的接口从请求头 **`X-Username`** 读取操作者；**缺省值为 `admin`**。
- 依据用户名查找 `User`；用户不存在时回退到系统首个用户（便于本地免配置调试）。
- 权限模型：`admin` 可访问全部店铺；`operator` 仅能访问 `allowed_shop_ids` 中授权的店铺，越权返回 `403`。
- 密码存储：`sha256("amz::" + 明文)`（见 `app/auth.py`）。
- 生产环境应替换为 JWT/OAuth。

> 完整错误码与鉴权规则见 [`ERROR_CODES.md`](./ERROR_CODES.md)。

## 3. 接口一览

### 数据接入（`ingest`）

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| POST | /api/ingest/commit | 登录用户 | 确认映射并入库（生成数据版本，支持覆盖/追加） |
| GET | /api/ingest/issues | 登录用户 | 数据质量问题清单 |
| GET | /api/ingest/jobs | 登录用户 | 导入任务记录 |
| POST | /api/ingest/preview | 登录用户 | 上传广告报表并预览（解析表头、字段映射、逐行校验） |
| GET | /api/ingest/report-types | 登录用户 | 支持的报表类型清单 |
| POST | /api/ingest/rollback/{version_id} | 登录用户 | 回滚到指定数据版本 |
| GET | /api/ingest/versions | 登录用户 | 已入库的数据版本列表 |

### BI 分析（`bi`）

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | /api/bi/campaigns | 登录用户 | 广告活动清单（用于筛选器） |
| GET | /api/bi/drill | 登录用户 | 层级下钻（活动 → 广告组 → 关键词） |
| GET | /api/bi/metrics | 登录用户 | 统一指标口径（名称 / 单位 / 公式说明） |
| GET | /api/bi/overview | 登录用户 | 概览与环比（当期 vs 上期） |
| GET | /api/bi/query | 登录用户 | 指标聚合查询（按维度分组 + 筛选 + 排序 + 分页） |
| GET | /api/bi/range | 登录用户 | 可用数据日期范围 |
| GET | /api/bi/shops | 登录用户 | 当前用户可访问的店铺（含站点 / 币种 / 时区） |
| GET | /api/bi/trend | 登录用户 | 指标按日趋势 |

### 智能分析（`analysis`）

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | /api/analysis/compare | 登录用户 | 重取多模型对比结果 |
| GET | /api/analysis/dimensions | 登录用户 | 12 个分析维度定义 |
| GET | /api/analysis/dsl/meta | 登录用户 | DSL 规则构建器元数据（指标 / 运算符 / 作用域 / 维度） |
| GET | /api/analysis/dsl/validate | 登录用户 | 校验 DSL 规则文本并返回解析结果 |
| POST | /api/analysis/items/{iid}/execute | 登录用户 | 执行建议项动作 |
| GET | /api/analysis/items/{iid}/execution | 登录用户 | 查询建议项执行结果 |
| POST | /api/analysis/items/{iid}/status | 登录用户 | 更新建议项状态（采纳 / 忽略等） |
| GET | /api/analysis/prompt | 登录用户 | 获取提示词模板 |
| PUT | /api/analysis/prompt | 登录用户 | 保存提示词模板 |
| GET | /api/analysis/providers | 登录用户 | 模型 / 运行配置清单 |
| POST | /api/analysis/providers | 登录用户 | 新增或更新模型配置 |
| DELETE | /api/analysis/providers/{pid} | 登录用户 | 删除模型配置 |
| POST | /api/analysis/providers/{pid}/test | 登录用户 | 测试模型连通性 |
| GET | /api/analysis/retro | 登录用户 | 复盘数据 |
| GET | /api/analysis/rules | 登录用户 | 规则清单 |
| POST | /api/analysis/rules | 登录用户 | 新建规则 |
| DELETE | /api/analysis/rules/{rid} | 登录用户 | 删除规则 |
| PUT | /api/analysis/rules/{rid} | 登录用户 | 更新规则（启用 / 条件 / 优先级 / 模板 / DSL） |
| POST | /api/analysis/run | 登录用户 | 运行分析（规则引擎 / 单模型 LLM / 多模型对比） |
| GET | /api/analysis/runs | 登录用户 | 历史运行记录 |
| GET | /api/analysis/runs/{rid} | 登录用户 | 单次运行详情（含建议项） |

### 库存健康（`inventory`）

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | /api/inventory | 登录用户 | 库存健康概览（可售天数、断货风险） |

### 知识库（`kb`）

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | /api/kb/aba/terms | 登录用户 | ABA 搜索词热度数据 |
| GET | /api/kb/changes/log | 登录用户 | 知识库变更日志 |
| POST | /api/kb/import | 登录用户 | 批量导入记录 |
| POST | /api/kb/rank/from-aba | 登录用户 | 从 ABA 数据生成排名记录 |
| GET | /api/kb/rank/trend | 登录用户 | 关键词排名趋势 |
| GET | /api/kb/{entity} | 登录用户 | 列出知识库实体（关键词 / 竞品 / 排名等） |
| POST | /api/kb/{entity} | 登录用户 | 新增知识库记录 |
| GET | /api/kb/{entity}/export | 登录用户 | 导出知识库为 CSV |
| DELETE | /api/kb/{entity}/{eid} | 登录用户 | 删除知识库记录 |
| PUT | /api/kb/{entity}/{eid} | 登录用户 | 更新知识库记录 |

### 新品上市（`launch`）

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| POST | /api/launch/generate | 登录用户 | 生成新品上市方案（含节点） |
| POST | /api/launch/nodes | 登录用户 | 新增节点 |
| DELETE | /api/launch/nodes/{nid} | 登录用户 | 删除节点 |
| PUT | /api/launch/nodes/{nid} | 登录用户 | 更新节点 |
| GET | /api/launch/projects | 登录用户 | 上市方案清单 |
| GET | /api/launch/projects/{pid} | 登录用户 | 方案详情（含节点） |
| GET | /api/launch/projects/{pid}/export | 登录用户 | 导出方案（CSV / JSON） |

### 协作评论（`comment`）

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | /api/comment | 登录用户 | 列出评论（按对象维度） |
| POST | /api/comment | 登录用户 | 发表评论 |
| DELETE | /api/comment/{cid} | 登录用户 | 删除评论（仅本人） |
| PUT | /api/comment/{cid} | 登录用户 | 编辑评论（仅本人） |

### 告警推送（`notify`）

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | /api/notify/channels | 登录用户 | 告警渠道清单 |
| POST | /api/notify/channels | 登录用户 | 新增渠道 |
| DELETE | /api/notify/channels/{cid} | 登录用户 | 删除渠道 |
| PUT | /api/notify/channels/{cid} | 登录用户 | 更新渠道 |
| GET | /api/notify/logs | 登录用户 | 推送记录 |
| POST | /api/notify/test | 登录用户 | 发送测试消息 |

### 系统管理（`admin`）

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | /api/admin/audit | 管理员 | 操作审计日志 |
| POST | /api/admin/login | 公开 | 用户名密码登录 |
| GET | /api/admin/shops | 管理员 | 店铺清单 |
| POST | /api/admin/shops | 管理员 | 新增店铺 |
| GET | /api/admin/usage | 管理员 | 用量统计 |
| GET | /api/admin/users | 管理员 | 用户清单 |
| POST | /api/admin/users | 管理员 | 新增 / 更新用户 |
| DELETE | /api/admin/users/{uid} | 管理员 | 删除用户 |

### 系统（`default`）

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | /api/health | 公开 | 健康检查 |

## 4. 接口详情

### 数据接入（`ingest`）

广告报表上传、字段映射预览、入库与数据版本管理。

#### `POST` /api/ingest/commit

**确认映射并入库（生成数据版本，支持覆盖/追加）**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**请求体**（`application/json`）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| tmp_path | string | 是 | - |
| shop_id | integer | 否 | 默认 `1` |
| report_type | string | 是 | - |
| mapping | map<any> | 是 | - |
| strategy | string | 否 | 默认 `append` |
| file_name | string | 否 | 默认 `` |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `GET` /api/ingest/issues

**数据质量问题清单**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `job_id` | query | integer | 是 | - |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `GET` /api/ingest/jobs

**导入任务记录**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `shop_id` | query | integer | 否 | 店铺 ID，可重复传多个；缺省为当前用户可访问的全部店铺 |
| `limit` | query | integer | 否 | 返回条数上限 默认 `50` |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `POST` /api/ingest/preview

**上传广告报表并预览（解析表头、字段映射、逐行校验）**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**请求体**（`multipart/form-data`）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| shop_id | integer | 否 | 默认 `1` |
| file | string | 是 | - |
| report_type | string | 否 | 默认 `` |
| custom_mapping | string | 否 | 默认 `` |

**成功响应**：`200`

返回结构：

```json
{"tmp_path": "...", "columns": [...], "mapping": {...}, "sample": [...], "issues": [...]}
```

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `GET` /api/ingest/report-types

**支持的报表类型清单**

- 权限：**登录用户**

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `POST` /api/ingest/rollback/{version_id}

**回滚到指定数据版本**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `version_id` | path | integer | 是 | 数据版本 ID |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `GET` /api/ingest/versions

**已入库的数据版本列表**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `shop_id` | query | integer | 否 | 店铺 ID，可重复传多个；缺省为当前用户可访问的全部店铺 |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

### BI 分析（`bi`）

广告投放指标的聚合查询、趋势、结构与下钻。

#### `GET` /api/bi/campaigns

**广告活动清单（用于筛选器）**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `shop_id` | query | array<integer>? | 否 | 店铺 ID，可重复传多个；缺省为当前用户可访问的全部店铺 |
| `marketplace` | query | string | 否 | 站点代码（如 `US`） |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

返回结构：

```json
{"items": [{"id", "name"} ...]}
```

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `GET` /api/bi/drill

**层级下钻（活动 → 广告组 → 关键词）**

- 权限：**登录用户**
- 补充：层级下钻：活动 → 广告组 → 关键词。

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `shop_id` | query | array<integer>? | 否 | 店铺 ID，可重复传多个；缺省为当前用户可访问的全部店铺 |
| `marketplace` | query | string | 否 | 站点代码（如 `US`） |
| `start` | query | string | 否 | 起始日期，格式 `YYYY-MM-DD`（缺省取可用范围起点） |
| `end` | query | string | 否 | 结束日期，格式 `YYYY-MM-DD`（缺省取可用范围终点） |
| `campaign_id` | query | string | 否 | 广告活动 ID（下钻起点） |
| `adgroup_id` | query | string | 否 | 广告组 ID（进一步下钻到关键词） |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

返回结构：

```json
{"level": "campaign | adgroup | keyword", "rows": [{...}]}
```

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `GET` /api/bi/metrics

**统一指标口径（名称 / 单位 / 公式说明）**

- 权限：**登录用户**

**成功响应**：`200`

返回结构：

```json
{"items": [{"code", "name_zh", "unit", "desc"} ...]}
```

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `GET` /api/bi/overview

**概览与环比（当期 vs 上期）**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `shop_id` | query | array<integer>? | 否 | 店铺 ID，可重复传多个；缺省为当前用户可访问的全部店铺 |
| `marketplace` | query | string | 否 | 站点代码（如 `US`） |
| `days` | query | integer | 否 | 统计天数（用于环比 / 用量窗口） 默认 `30` |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

返回结构：

```json
{"period": ["起", "止"], "current": {<指标>}, "previous": {<指标>}, "delta": {<指标>}, "shop_ids": [1]}
```

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `GET` /api/bi/query

**指标聚合查询（按维度分组 + 筛选 + 排序 + 分页）**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `shop_id` | query | array<integer>? | 否 | 店铺 ID，可重复传多个；缺省为当前用户可访问的全部店铺 |
| `marketplace` | query | string | 否 | 站点代码（如 `US`） |
| `start` | query | string | 否 | 起始日期，格式 `YYYY-MM-DD`（缺省取可用范围起点） |
| `end` | query | string | 否 | 结束日期，格式 `YYYY-MM-DD`（缺省取可用范围终点） |
| `group_by` | query | string | 否 | 聚合维度，如 `campaign` / `adgroup` / `keyword` / `ad_format` / `placement` / `targeting` 默认 `campaign` |
| `filters` | query | string | 否 | 过滤条件，JSON 字符串（如 `{"campaign_ids":["C1"]}`） |
| `sort_by` | query | string | 否 | 排序字段 默认 `spend` |
| `sort_dir` | query | string | 否 | 排序方向：`asc` / `desc` 默认 `desc` |
| `page` | query | integer | 否 | 页码，从 1 开始 默认 `1` |
| `size` | query | integer | 否 | 每页条数 默认 `100` |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

返回结构：

```json
{"rows": [{<group_by 维度列>, <指标字段...>}], "total": 123, "summary": {<指标>}, "total_sales": 0.0, "group_by": "campaign", "shop_ids": [1]}
```

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `GET` /api/bi/range

**可用数据日期范围**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `shop_id` | query | array<integer>? | 否 | 店铺 ID，可重复传多个；缺省为当前用户可访问的全部店铺 |
| `marketplace` | query | string | 否 | 站点代码（如 `US`） |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

返回结构：

```json
{"start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "shop_ids": [1, 2]}
```

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `GET` /api/bi/shops

**当前用户可访问的店铺（含站点 / 币种 / 时区）**

- 权限：**登录用户**
- 补充：当前用户可访问的店铺清单（含 marketplace / currency / timezone）。

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

返回结构：

```json
{"items": [{"id", "name", "marketplace", "currency", "timezone"} ...]}
```

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `GET` /api/bi/trend

**指标按日趋势**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `shop_id` | query | array<integer>? | 否 | 店铺 ID，可重复传多个；缺省为当前用户可访问的全部店铺 |
| `marketplace` | query | string | 否 | 站点代码（如 `US`） |
| `start` | query | string | 否 | 起始日期，格式 `YYYY-MM-DD`（缺省取可用范围起点） |
| `end` | query | string | 否 | 结束日期，格式 `YYYY-MM-DD`（缺省取可用范围终点） |
| `filters` | query | string | 否 | 过滤条件，JSON 字符串（如 `{"campaign_ids":["C1"]}`） |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

返回结构：

```json
{"points": [{"date", "spend", "sales", "acos", "orders"} ...], "summary": {<指标>}}
```

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

### 智能分析（`analysis`）

多模型/规则引擎运行、建议审阅、规则与模型配置管理。

#### `GET` /api/analysis/compare

**重取多模型对比结果**

- 权限：**登录用户**
- 补充：按对比分组号重新拉取多模型对比结果（用于刷新 / 复盘查看）。

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `group` | query | string | 否 | 多模型对比分组 ID |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

返回结构：

```json
{"mode": "compare", "results": [{"provider": {...}, "items": [...]}], "summary": {...}}
```

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `GET` /api/analysis/dimensions

**12 个分析维度定义**

- 权限：**登录用户**

**成功响应**：`200`

返回结构：

```json
{"items": [{"code", "name_zh"} ...]}
```

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `GET` /api/analysis/dsl/meta

**DSL 规则构建器元数据（指标 / 运算符 / 作用域 / 维度）**

- 权限：**登录用户**

**成功响应**：`200`

返回结构：

```json
{"metrics": [...], "ops": [...], "scopes": [...], "dimensions": [...], "severities": [...]}
```

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `GET` /api/analysis/dsl/validate

**校验 DSL 规则文本并返回解析结果**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `text` | query | string | 否 | 待校验的 DSL 规则文本 |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

返回结构：

```json
{"ok": true, "errors": [], "parsed": {<解析结果>}}
```

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `POST` /api/analysis/items/{iid}/execute

**执行建议项动作**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `iid` | path | integer | 是 | 建议项 ID |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**请求体**（`application/json`）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| change_note | string | 否 | 默认 `` |
| before_days | integer | 否 | 默认 `7` |
| after_days | integer | 否 | 默认 `7` |
| exec_date | string | 否 | 默认 `` |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `GET` /api/analysis/items/{iid}/execution

**查询建议项执行结果**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `iid` | path | integer | 是 | 建议项 ID |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `POST` /api/analysis/items/{iid}/status

**更新建议项状态（采纳 / 忽略等）**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `iid` | path | integer | 是 | 建议项 ID |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**请求体**（`application/json`）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| status | string | 是 | - |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `GET` /api/analysis/prompt

**获取提示词模板**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `code` | query | string | 否 | 代码 / 标识（如规则 code、提示词 code） 默认 `default` |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `PUT` /api/analysis/prompt

**保存提示词模板**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**请求体**（`application/json`）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| code | string | 否 | 默认 `default` |
| content | string | 否 | 默认 `` |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `GET` /api/analysis/providers

**模型 / 运行配置清单**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

返回结构：

```json
{"items": [{"id", "name", "kind", "endpoint", "model", "enabled"} ...]}
```

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `POST` /api/analysis/providers

**新增或更新模型配置**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**请求体**（`application/json`）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | integer? | 否 | - |
| name | string | 否 | 默认 `default` |
| endpoint | string | 否 | 默认 `` |
| model | string | 否 | 默认 `` |
| api_key | string | 否 | 默认 `` |
| params | map<any> | 否 | 默认 `{}` |
| enabled | boolean | 否 | 默认 `False` |
| is_default | boolean | 否 | 默认 `False` |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `DELETE` /api/analysis/providers/{pid}

**删除模型配置**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `pid` | path | integer | 是 | 模型配置 ID / 方案 ID |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `POST` /api/analysis/providers/{pid}/test

**测试模型连通性**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `pid` | path | integer | 是 | 模型配置 ID / 方案 ID |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `GET` /api/analysis/retro

**复盘数据**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `shop_id` | query | integer | 否 | 店铺 ID，可重复传多个；缺省为当前用户可访问的全部店铺 |
| `recompute` | query | integer | 否 | - 默认 `0` |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `GET` /api/analysis/rules

**规则清单**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

返回结构：

```json
{"items": [{"id", "code", "name_zh", "dimension", "enabled", "priority", "dsl_text"} ...]}
```

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `POST` /api/analysis/rules

**新建规则**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**请求体**（`application/json`）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| code | string | 是 | - |
| name_zh | string | 是 | - |
| dimension | string | 是 | - |
| dsl_text | string | 否 | 默认 `` |
| priority | integer | 否 | 默认 `5` |
| enabled | boolean | 否 | 默认 `True` |
| advice_template | string | 否 | 默认 `` |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `DELETE` /api/analysis/rules/{rid}

**删除规则**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `rid` | path | integer | 是 | 运行记录 ID / 规则 ID |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `PUT` /api/analysis/rules/{rid}

**更新规则（启用 / 条件 / 优先级 / 模板 / DSL）**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `rid` | path | integer | 是 | 运行记录 ID / 规则 ID |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**请求体**（`application/json`）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | integer | 是 | - |
| enabled | boolean? | 否 | - |
| condition | map<any>? | 否 | - |
| priority | integer? | 否 | - |
| advice_template | string? | 否 | - |
| dsl_text | string? | 否 | - |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `POST` /api/analysis/run

**运行分析（规则引擎 / 单模型 LLM / 多模型对比）**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**请求体**（`application/json`）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| shop_id | integer | 否 | 默认 `1` |
| start | string | 否 | 默认 `` |
| end | string | 否 | 默认 `` |
| target_acos | number | 否 | 默认 `35.0` |
| provider_id | integer? | 否 | - |
| use_llm | boolean | 否 | 默认 `True` |
| notify | boolean | 否 | 默认 `False` |
| provider_ids | array<integer> | 否 | 默认 `[]` |

**成功响应**：`200`

返回结构：

```jsonc
// 规则/单模型：
{"mode": "rule | llm", "items": [<建议项>], "run_id": 12}
// 多模型对比（provider_ids 非空）：
{"mode": "compare", "run_id": 12, "results": [{"provider": {...}, "items": [...]}], "summary": {"shared_dims": [...], "unique_dims": {...}, "dim_matrix": {...}}}
```

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `GET` /api/analysis/runs

**历史运行记录**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `shop_id` | query | integer | 否 | 店铺 ID，可重复传多个；缺省为当前用户可访问的全部店铺 |
| `limit` | query | integer | 否 | 返回条数上限 默认 `20` |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

返回结构：

```json
{"items": [{"id", "shop_id", "mode", "provider", "created_at", "item_count"} ...]}
```

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `GET` /api/analysis/runs/{rid}

**单次运行详情（含建议项）**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `rid` | path | integer | 是 | 运行记录 ID / 规则 ID |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

返回结构：

```json
{"run": {...}, "items": [<建议项>]}
```

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

### 库存健康（`inventory`）

库存周转、可售天数与断货风险概览。

#### `GET` /api/inventory

**库存健康概览（可售天数、断货风险）**

- 权限：**登录用户**
- 补充：返回每个 ASIN 的最新库存快照、可售天数、低库存与在投标识，以及汇总。

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `shop_id` | query | array<integer>? | 否 | 店铺 ID，可重复传多个；缺省为当前用户可访问的全部店铺 |
| `marketplace` | query | string | 否 | 站点代码（如 `US`） |
| `threshold` | query | number | 否 | - 默认 `14.0` |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

返回结构：

```json
{"items": [{"shop_id", "asin", "sku", "date", "qty", "inbound", "days_of_cover", "advertised", "low_stock"} ...], "summary": {"asin_count", "low_count", "advertised_low", "threshold"}}
```

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

### 知识库（`kb`）

关键词库、竞品库、Listing 与素材等知识的增删改查。

#### `GET` /api/kb/aba/terms

**ABA 搜索词热度数据**

- 权限：**登录用户**
- 补充：返回店铺内 ABA 高潜搜索词，供一键加入排名追踪。

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `shop_id` | query | integer | 否 | 店铺 ID，可重复传多个；缺省为当前用户可访问的全部店铺 |
| `limit` | query | integer | 否 | 返回条数上限 默认 `30` |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `GET` /api/kb/changes/log

**知识库变更日志**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `entity` | query | string | 否 | 知识库实体类型，如 `keyword` / `competitor` / `rank` / `listing` |
| `shop_id` | query | integer | 否 | 店铺 ID，可重复传多个；缺省为当前用户可访问的全部店铺 |
| `limit` | query | integer | 否 | 返回条数上限 默认 `200` |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `POST` /api/kb/import

**批量导入记录**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**请求体**（`application/json`）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| entity | string | 是 | - |
| shop_id | integer | 否 | 默认 `1` |
| rows | array<-> | 是 | - |
| mode | string | 否 | 默认 `append` |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `POST` /api/kb/rank/from-aba

**从 ABA 数据生成排名记录**

- 权限：**登录用户**
- 补充：从 ABA 高潜词一键新建排名追踪记录（默认排名留空，待回填实测值）。

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**请求体**（`application/json`）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| shop_id | integer | 否 | 默认 `1` |
| asin | string | 否 | 默认 `` |
| term | string | 是 | - |
| marketplace | string | 否 | 默认 `US` |
| rank_source | string | 否 | 默认 `aba` |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `GET` /api/kb/rank/trend

**关键词排名趋势**

- 权限：**登录用户**
- 补充：排名趋势时间序列：按 (asin, term, marketplace) 分组，附最新一周环比 delta 与掉落预警。

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `shop_id` | query | integer | 否 | 店铺 ID，可重复传多个；缺省为当前用户可访问的全部店铺 |
| `marketplace` | query | string | 否 | 站点代码（如 `US`） |
| `asin` | query | string | 否 | - |
| `term` | query | string | 否 | - |
| `limit` | query | integer | 否 | 返回条数上限 默认 `50` |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `GET` /api/kb/{entity}

**列出知识库实体（关键词 / 竞品 / 排名等）**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `entity` | path | string | 是 | 知识库实体类型，如 `keyword` / `competitor` / `rank` / `listing` |
| `shop_id` | query | integer | 否 | 店铺 ID，可重复传多个；缺省为当前用户可访问的全部店铺 |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

返回结构：

```json
{"items": [{...}], "total": 123}
```

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `POST` /api/kb/{entity}

**新增知识库记录**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `entity` | path | string | 是 | 知识库实体类型，如 `keyword` / `competitor` / `rank` / `listing` |
| `shop_id` | query | integer | 否 | 店铺 ID，可重复传多个；缺省为当前用户可访问的全部店铺 |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**请求体**（`application/json`）

类型：`map<any>`

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `GET` /api/kb/{entity}/export

**导出知识库为 CSV**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `entity` | path | string | 是 | 知识库实体类型，如 `keyword` / `competitor` / `rank` / `listing` |
| `shop_id` | query | integer | 否 | 店铺 ID，可重复传多个；缺省为当前用户可访问的全部店铺 |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `DELETE` /api/kb/{entity}/{eid}

**删除知识库记录**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `entity` | path | string | 是 | 知识库实体类型，如 `keyword` / `competitor` / `rank` / `listing` |
| `eid` | path | integer | 是 | 记录 ID |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `PUT` /api/kb/{entity}/{eid}

**更新知识库记录**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `entity` | path | string | 是 | 知识库实体类型，如 `keyword` / `competitor` / `rank` / `listing` |
| `eid` | path | integer | 是 | 记录 ID |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**请求体**（`application/json`）

类型：`map<any>`

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

### 新品上市（`launch`）

新品上市方案与节点（里程碑）管理。

#### `POST` /api/launch/generate

**生成新品上市方案（含节点）**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**请求体**（`application/json`）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| shop_id | integer | 否 | 默认 `1` |
| asin | string | 是 | - |
| title | string | 否 | 默认 `` |
| category | string | 否 | 默认 `` |
| target_acos | number | 否 | 默认 `35.0` |
| daily_budget | number | 否 | 默认 `60.0` |
| cycle_days | integer | 否 | 默认 `30` |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `POST` /api/launch/nodes

**新增节点**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `project_id` | query | integer | 是 | - |
| `parent_id` | query | integer | 否 | - |
| `node_type` | query | string | 否 | - 默认 `keyword` |
| `name` | query | string | 否 | - |
| `match_type` | query | string | 否 | - 默认 `exact` |
| `bid` | query | number | 否 | - 默认 `0.8` |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `DELETE` /api/launch/nodes/{nid}

**删除节点**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `nid` | path | integer | 是 | 节点 ID |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `PUT` /api/launch/nodes/{nid}

**更新节点**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `nid` | path | integer | 是 | 节点 ID |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**请求体**（`application/json`）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| name | string? | 否 | - |
| match_type | string? | 否 | - |
| bid | number? | 否 | - |
| budget | number? | 否 | - |
| note | string? | 否 | - |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `GET` /api/launch/projects

**上市方案清单**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `shop_id` | query | integer | 否 | 店铺 ID，可重复传多个；缺省为当前用户可访问的全部店铺 |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

返回结构：

```json
{"items": [{"id", "asin", "title", "status", "created_at"} ...]}
```

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `GET` /api/launch/projects/{pid}

**方案详情（含节点）**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `pid` | path | integer | 是 | 模型配置 ID / 方案 ID |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `GET` /api/launch/projects/{pid}/export

**导出方案（CSV / JSON）**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `pid` | path | integer | 是 | 模型配置 ID / 方案 ID |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

### 协作评论（`comment`）

建议/对象上的评论线程（协作讨论）。

#### `GET` /api/comment

**列出评论（按对象维度）**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `entity_type` | query | string | 是 | - |
| `entity_id` | query | integer | 是 | - |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

返回结构：

```json
{"items": [{"id", "object_type", "object_id", "content", "author", "created_at"} ...]}
```

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `POST` /api/comment

**发表评论**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**请求体**（`application/json`）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| entity_type | string | 是 | - |
| entity_id | integer | 是 | - |
| text | string | 是 | - |
| shop_id | integer | 否 | 默认 `0` |
| parent_id | integer | 否 | - |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `DELETE` /api/comment/{cid}

**删除评论（仅本人）**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `cid` | path | integer | 是 | 渠道 ID / 评论 ID |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `PUT` /api/comment/{cid}

**编辑评论（仅本人）**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `cid` | path | integer | 是 | 渠道 ID / 评论 ID |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**请求体**（`application/json`）

类型：`map<any>`

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

### 告警推送（`notify`）

告警渠道配置、测试与推送记录。

#### `GET` /api/notify/channels

**告警渠道清单**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

返回结构：

```json
{"items": [{"id", "name", "chan_type", "url", "enabled"} ...]}
```

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `POST` /api/notify/channels

**新增渠道**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**请求体**（`application/json`）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| name | string | 是 | - |
| chan_type | string | 是 | - |
| shop_id | integer | 否 | 默认 `1` |
| config | map<any> | 否 | 默认 `{}` |
| enabled | boolean? | 否 | 默认 `True` |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `DELETE` /api/notify/channels/{cid}

**删除渠道**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `cid` | path | integer | 是 | 渠道 ID / 评论 ID |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `PUT` /api/notify/channels/{cid}

**更新渠道**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `cid` | path | integer | 是 | 渠道 ID / 评论 ID |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**请求体**（`application/json`）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| name | string? | 否 | - |
| chan_type | string? | 否 | - |
| config | map<any>? | 否 | - |
| enabled | boolean? | 否 | - |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `GET` /api/notify/logs

**推送记录**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `shop_id` | query | integer? | 否 | 店铺 ID，可重复传多个；缺省为当前用户可访问的全部店铺 |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

返回结构：

```json
{"items": [{"id", "channel", "status", "message", "created_at"} ...]}
```

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `POST` /api/notify/test

**发送测试消息**

- 权限：**登录用户**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**请求体**（`application/json`）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| channel_id | integer | 是 | - |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

### 系统管理（`admin`）

登录、用户管理与权限。

#### `GET` /api/admin/audit

**操作审计日志**

- 权限：**管理员**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `limit` | query | integer | 否 | 返回条数上限 默认 `100` |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `POST` /api/admin/login

**用户名密码登录**

- 权限：**公开**

**请求体**（`application/json`）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| username | string | 是 | - |
| password | string | 是 | - |

**成功响应**：`200`

返回结构：

```json
{"ok": true, "user": {"id", "username", "full_name", "role", "shop_ids", "quota_tokens", "quota_cost"}}
```

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `GET` /api/admin/shops

**店铺清单**

- 权限：**管理员**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

返回结构：

```json
{"items": [{"id", "name", "marketplace", "currency", "timezone"} ...]}
```

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `POST` /api/admin/shops

**新增店铺**

- 权限：**管理员**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**请求体**（`application/json`）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| name | string | 是 | - |
| marketplace | string | 否 | 默认 `US` |
| currency | string | 否 | 默认 `USD` |
| timezone | string | 否 | 默认 `America/New_York` |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `GET` /api/admin/usage

**用量统计**

- 权限：**管理员**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `days` | query | integer | 否 | 统计天数（用于环比 / 用量窗口） 默认 `30` |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `GET` /api/admin/users

**用户清单**

- 权限：**管理员**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

返回结构：

```json
{"items": [{"id", "username", "full_name", "role", "status", "shop_ids", "quota_tokens", "used_tokens", "used_cost", "created_at"} ...]}
```

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `POST` /api/admin/users

**新增 / 更新用户**

- 权限：**管理员**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**请求体**（`application/json`）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | integer? | 否 | - |
| username | string | 是 | - |
| password | string | 否 | 默认 `` |
| full_name | string | 否 | 默认 `` |
| role | string | 否 | 默认 `operator` |
| status | string | 否 | 默认 `active` |
| shop_ids | array<-> | 否 | 默认 `[]` |
| quota_tokens | integer | 否 | 默认 `2000000` |
| quota_cost | number | 否 | 默认 `200.0` |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

#### `DELETE` /api/admin/users/{uid}

**删除用户**

- 权限：**管理员**

**参数**

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `uid` | path | integer | 是 | 用户 ID |
| `X-Username` | header | string | 否 | 操作者用户名（缺省 `admin`） |

**成功响应**：`200`

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

### 系统（`default`）

健康检查等基础接口。

#### `GET` /api/health

**健康检查**

- 权限：**公开**

**成功响应**：`200`

返回结构：

```json
{"ok": true, "service": "amz-ad-workbench", "version": "0.1.0"}
```

**可能错误**：`400` 参数/业务校验失败 · `401` 未认证 · `403` 无权限 · `404` 资源不存在 · `409` 冲突 · `422` 请求体校验失败

---

_本文档由 `backend/scripts/gen_api_docs.py` 依据 OpenAPI 规范生成；接口变更后请重新生成以保持同步。_
