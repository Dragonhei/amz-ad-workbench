# AI 广告分析工作台（Amazon Ads Workbench）

面向**亚马逊卖家**的一站式广告分析工作台：把分散的广告报表变成可下钻的 BI 看板、可溯源的 AI 优化方案、可复用的知识库，以及新品冷启动的广告架构生成器。全中文界面，前后端一体、开箱即跑。

> 覆盖六大模块：**数据投喂 · AI 分析 · BI 看板 · 知识库 · 新品冷启动 · 多用户与配额**

---

## 目录

- [功能特性](#功能特性)
- [技术栈](#技术栈)
- [系统架构](#系统架构)
- [目录结构](#目录结构)
- [快速开始](#快速开始)
- [默认账号](#默认账号)
- [六大模块详解](#六大模块详解)
- [API 接口一览](#api-接口一览)
- [数据接入指南](#数据接入指南)
- [配置 AI 模型](#配置-ai-模型)
- [测试](#测试)
- [部署与数据库切换](#部署与数据库切换)
- [已知限制](#已知限制)
- [许可证与贡献](#许可证与贡献)

---

## 功能特性

- **报表即传即解析**：上传 CSV/TSV/XLSX，自动识别报表类型与字段映射，行级异常清单可下载、可回滚。
- **12 维 AI 分析**：预算 / 竞价 / 加词 / 减词 / 否定词 / 投放位置 / 结构 / Listing / 库存 / 排期 / 竞品 / 风险，每条结论**绑定 evidence（指标路径 + 数据快照）**，无证据不展示。
- **LLM 可配置 + 自动降级**：支持任意 OpenAI 兼容端点（Endpoint / 模型名 / API Key），未配置 Key 或调用失败时**自动降级到内置规则引擎**，永不空窗。
- **BI 三级下钻**：时间 / 活动 / 广告组 / 关键词 多维下钻，11 项指标筛选排序，趋势图与明细表点击联动。
- **知识库复用**：关键词库、CPC 竞价库、排名追踪、竞品库，支持增删改查 + CSV 批量导入导出 + 全量变更记录。
- **新品冷启动器**：复用知识库与 ABA 词，一键生成四活动广告架构（自动 / 精准 / 词组 / 商品定位），竞价取 CPC 库基准 × 匹配系数，可逐节点编辑并导出 Bulk Sheet。
- **多用户与配额**：管理员建号、分配店铺数据权限与 API 配额，记录调用量、Token、成本与审计日志。
- **多店铺 / 多站点**：顶部可多选店铺（US / DE / UK …），BI 看板与趋势支持**跨店汇总**与按 `marketplace` 站点过滤；金额按各店铺币种（USD / EUR / GBP …）自动格式化，店铺含 `timezone` 用于站点级周期对齐。
- **SP / SB / SD 全支持**：商品推广、品牌推广（Sponsored Brands）、展示型推广（Sponsored Display）报表统一解析入库。BI 看板可按 **广告格式（SP/SB/SD）**、**投放位置（Top of Search / Product Pages …）**、**定向（Targeting）** 自由下钻；SB 落地页 / 创意 / 标题、SD 受众 / 商品定向 ASIN 等专属维度完整落库。
- **库存联动预警**：上传库存报表（可售 / 在途 / 可售天数）后，「库存预警」页按 ASIN 展示最新库存快照与可售天数；对**仍在投广告且可售天数低于阈值**的 ASIN 高优告警（建议降预算 / 补货），并联动 AI 分析的「库存联动」维度产出 P0 结论。
- **排名追踪与竞品库**：知识库「排名追踪」按 **ASIN / 关键词 / 站点（marketplace）/ 来源（manual·aba·import）** 记录自然与广告排名；「排名趋势」页用 ECharts 折线展示排名随时间的走势（排名轴倒序，越靠上越好），自动高亮**较上周下跌 ≥ 3 名**的对象并列出掉落预警；「竞品 ASIN/品牌库」沉淀竞品价格 / 评分 / 卖点。ABA 高潜词可**一键加入排名追踪**，并联动 AI 分析的「竞品应对」维度产出排名掉落预警。
- **规则可视化 DSL（自定义告警/动作）**：在「分析」页用可视化表单（选指标 + 运算符 + 阈值 + 作用域 + 维度 + 严重度 + 模板）实时生成规则 DSL——`WHEN <指标> <运算符> <阈值> [FOR <作用域>] THEN [SUGGEST] <维度> "<模板>" [WITH SEVERITY <high|mid|low>]`，支持即时语法/语义校验；保存后**运行时自动参与分析**，命中即产出对应维度的可执行结论（带数据证据），非工程师也能维护投放规则。内置示例规则演示 ACOS 超阈与 CTR 偏低场景。
- **方案执行回填与效果复盘（闭环）**：对每条行动项点「执行并回填」，填写实际执行日期、前后回看天数与改动说明，系统自动记录**执行前后 N 天整体指标快照（ACOS / TACOS / CVR / CTR / 花费 / 销售额 / 订单等）**；「效果复盘」页用 ECharts 对比前后 ACOS，并以表格呈现各指标**环比与改善方向**（红涨=改善），把"分析 → 执行 → 复盘"串成完整闭环。
- **协作评论**：在「分析」页行动项「结论依据」抽屉内可直接**讨论结论**——发表评论、对评论做一级回复、删除自己的评论（级联删除回复）；`Comment` 模型以 (entity_type, entity_id) 为维度通用挂载，后续可复用到知识库 / 分析运行等实体。
- **告警推送（P2-3）**：在「告警推送」页配置可插拔的**通知渠道**（Webhook / 钉钉 / 企业微信 / Slack / 邮件），在分析页勾选「运行并推送告警」后，系统自动把 **P0/P1 级高优结论**推送到所有启用渠道，并在「推送历史」留存审计记录（状态 / 条数 / 详情）。Webhook 真实外发，`loopback://` 前缀可用于本地联调模拟；邮件在无 SMTP 时标记为模拟发送。
- **多模型对比（P2-2）**：在「分析」页「多模型对比」Tab 中，用同一份数据**并跑多个模型配置**（如不同 LLM 或本地 `mock://` 模拟模型），返回每个模型的独立分析运行，并以**并排卡片 + 维度差异摘要**呈现——自动标出各模型共同覆盖的维度与仅某一模型独有的维度（diff 高亮）。每个模型产出独立 `AnalysisRun`（通过 `compare_group` 关联），可凭分组号随时重新拉取对比结果；未配置真实 Key 的模型自动降级到规则引擎，结果仍纳入对比。

---

## 技术栈

| 层 | 技术 | 版本要求 |
|---|---|---|
| 后端 | Python + FastAPI + SQLAlchemy + SQLite（可切 PostgreSQL） | Python ≥ 3.10 |
| 异步服务 | Uvicorn | ≥ 0.27 |
| 数据校验 | Pydantic | ≥ 2.6 |
| HTTP 客户端 | HTTPX（LLM 调用） | ≥ 0.27 |
| 表格解析 | openpyxl（XLSX）/ csv（CSV/TSV） | ≥ 3.1 |
| 前端 | React 18 + Ant Design 5 + ECharts 5 + TanStack Table | Node ≥ 18 |
| 构建 | Vite 5 | — |
| 路由 | React Router 6 | — |

---

## 系统架构

```
 报表 (CSV / TSV / XLSX)
        │
        ▼
 ┌──────────────────────────────────────────────────────────┐
 │ 数据投喂层  ingest                                          │
 │  类型识别(表头指纹+文件名) → 字段映射(精确/包含/模糊) → 行级校验 │
 └──────────────────────────────────────────────────────────┘
        │  写入
        ▼
 统一事实表 fact_ad_perf / fact_search_term / fact_aba
            / fact_brand_metric / fact_listing_daily
        │
        ├──────────────┬──────────────────────┬─────────────────┐
        ▼              ▼                      ▼                 ▼
   BI 看板          AI 分析(规则/LLM)      知识库(词/竞价/      多用户/权限/配额
   (下钻+趋势)      12 维行动项+evidence     排名/竞品)         (X-Username 演示鉴权)
        │              │                      │
        │              ▼                      │
        │      结论可追溯到数据证据            │
        │              │                      │
        └──────────────┴─────▶ 新品冷启动 ◀───┘
                    (复用知识库 + ABA 词生成四活动架构)
```

数据模型采用七层设计：**平台层（Org/Shop/User）→ 接入层（SourceFile/IngestJob/FieldMapping/ParseIssue/DatasetVersion）→ 事实层（各 fact 表）→ 派生层（MetricDefinition）→ 分析层（LlmProvider/AnalysisRule/PromptTemplate/AnalysisRun/ActionItem/Evidence）→ 知识层（Kb*）→ 冷启动层（Launch*）**。

---

## 目录结构

```
amz-ad-workbench/
├── backend/
│   ├── app/
│   │   ├── models.py        # 七层 ORM 模型（约 30 张表）
│   │   ├── parsers.py       # 报表解析引擎：编码探测/表头定位/类型识别/字段映射/值清洗/行级校验
│   │   ├── metrics.py       # 统一指标口径（11 项）与聚合查询
│   │   ├── rules.py         # 12 维维度定义 + 内置规则引擎（LLM 兜底）
│   │   ├── llm.py           # OpenAI 兼容调用、重试退避、JSON 强约束、Key 混淆存储
│   │   ├── auth.py          # 极简鉴权与数据权限校验
│   │   ├── seed.py          # 种子数据（账号/规则/知识库示例）
│   │   ├── db.py            # 引擎与 Session
│   │   ├── main.py          # 应用入口（含前端托管）
│   │   └── routers/         # ingest / bi / analysis / kb / launch / admin
│   ├── samples/             # 示例报表生成器（含人为注入的脏数据）
│   ├── data/                # SQLite 库与上传临时文件（已 gitignore）
│   ├── requirements.txt     # 后端依赖
│   ├── run.py               # Uvicorn 启动入口
│   ├── seed_data.py         # 灌入 5 份示例报表（演示数据）
│   └── test_e2e.py          # 端到端冒烟测试（31 项断言）
├── frontend/
│   ├── src/pages/           # Dashboard / Ingest / Analysis / Bi / Knowledge / Launch / Admin
│   ├── package.json
│   └── vite.config.js
├── .github/workflows/ci.yml # CI：后端 e2e + 前端构建
├── start.bat                # Windows 一键启动（后端）
├── LICENSE                  # MIT
└── README.md
```

---

## 快速开始

### 方式一：仅后端（最快验证 API）

```bash
cd backend
pip install -r requirements.txt      # 安装依赖
python run.py                        # 首次启动自动建表 + 写入种子数据
# 可选：灌入 5 份示例广告报表（BI/分析演示用）
python seed_data.py
# 浏览器打开 http://127.0.0.1:8000/api/health 看到 {"ok": true} 即成功
```

> 注：`frontend/dist` 未构建时，后端只提供 API，不托管界面（已做优雅降级，不会崩溃）。

### 方式二：前后端一体（推荐）

```bash
# 1) 前端构建
cd frontend
npm install
npm run build          # 产物输出到 frontend/dist

# 2) 启动后端（自动托管 frontend/dist，访问 8000 即可）
cd ../backend
pip install -r requirements.txt
python run.py
# 打开 http://127.0.0.1:8000
```

### 方式三：前端开发模式

```bash
# 终端 A
cd backend && pip install -r requirements.txt && python run.py
# 终端 B
cd frontend && npm install && npm run dev   # http://127.0.0.1:5173，已代理 /api → 8000
```

### Windows 一键启动

双击根目录 `start.bat`（会自动探测本机 `python`/`python3` 并启动后端）。完整界面需先按"方式二"构建前端。

---

## 默认账号

| 角色 | 用户名 | 密码 | 权限 |
|---|---|---|---|
| 管理员 | `admin` | `admin123` | 全部店铺数据权限、可管理用户/店铺/配额 |
| 运营 | `operator` | `123456` | 仅被授权的店铺（演示中为店铺 1） |

右上角可随时切换账号，用于验证**数据权限隔离**效果。

> 鉴权当前为演示用的 `X-Username` 请求头，生产环境请替换为 JWT/OAuth（见已知限制）。

---

## 六大模块详解

### 1. 数据投喂（ingest）
上传广告报表 → 自动识别类型与置信度 → 字段映射可手工调整 → 行级异常清单 → 覆盖/追加/跳过写入 → 数据版本可回滚。
- 支持的报表类型：SP 广告报表、搜索词报表（ST）、业务报告（BR）、ABA 搜索词报告、品牌指标报告（BIZ）。
- 报表格式错误时不阻断：自动跳过前导说明行，表头走别名表 + 模糊匹配；`$`/`,`/`%`/负数/空值/多格式日期与 Excel 序列号均有清洗器；异常行进 `parse_issue` 可查看、可下载。

### 2. AI 分析（analysis）
- 模型可配（Endpoint / 模型名 / API Key），提示词与规则可编辑。
- 输出 **12 维结构化方案**，每条结论绑定 `evidence`（指标路径 + 数据快照）；未配置 Key 或调用失败自动降级到内置规则引擎。
- API 调用失败处理：401/403 立即失败；超时/429/5xx 指数退避重试 3 次；输出非 JSON 时自动修复重试一次，仍失败则降级；相同输入按指纹缓存，避免重复计费。

### 3. BI 看板（bi）
时间 / 活动 / 广告组 / 关键词 下钻，11 项指标（曝光/点击/CTR/CVR/花费/ACOS/TACOS/订单/销售额/CPC/ROI 等）筛选排序，趋势图与明细表点击联动。TACOS 分母来自业务报告的总销售额。

### 4. 知识库（kb）
关键词库、CPC 竞价库、排名追踪、竞品库；增删改查 + CSV 批量导入导出 + 全量变更记录（`KbChangeLog`）。

### 5. 新品冷启动（launch）
复用知识库与 ABA 词生成四活动架构：自动投放（25%）/ 精准（40%）/ 词组（20%）/ 商品定位 SD（15%）；竞价取 CPC 库基准 × 匹配系数；可逐节点编辑并导出 **Bulk Sheet**（可直接上传亚马逊后台）。

### 6. 多用户（admin）
管理员建号、分配店铺数据权限与 API 配额，记录调用量、Token、成本与审计日志。

---

## API 接口一览

所有接口前缀为 `/api`，鉴权演示用请求头 `X-Username`。健康检查在 `/api/health`。

### 数据投喂 `/api/ingest`
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/report-types` | 支持的报表类型 |
| POST | `/preview` | 上传并预览（类型识别 + 字段映射 + 异常） |
| POST | `/commit` | 提交写入（覆盖/追加/跳过） |
| GET | `/jobs` | 接入任务列表 |
| GET | `/issues` | 行级异常清单 |
| GET | `/versions` | 数据版本 |
| POST | `/rollback/{version_id}` | 回滚到某版本 |

### BI 看板 `/api/bi`
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/metrics` | 可选指标定义 |
| GET | `/shops` | 当前用户可访问的店铺清单（含 `marketplace` / `currency` / `timezone`） |
| GET | `/range` | 数据日期范围 |
| GET | `/campaigns` | 活动列表 |
| GET | `/query` | 聚合查询（group_by/筛选/排序） |
| GET | `/trend` | 每日趋势 |
| GET | `/overview` | 总览指标卡 |
| GET | `/drill` | 三级下钻 |

> **多店铺 / 多站点**：`/range`、`/campaigns`、`/query`、`/trend`、`/overview`、`/drill` 均接受
> `shop_id` 为**可重复列表参数**（`?shop_id=1&shop_id=2`）与可选 `marketplace` 过滤（`?marketplace=DE`）。
> 不传 `shop_id` 时取当前用户被授权的全部店铺；越权店铺返回 403。

### AI 分析 `/api/analysis`
| 方法 | 路径 | 说明 |
|---|---|---|
| GET/POST | `/providers` | LLM 提供商列表 / 新增 |
| DELETE | `/providers/{pid}` | 删除提供商 |
| POST | `/providers/{pid}/test` | 连通性测试 |
| GET/PUT | `/rules`、`/rules/{rid}` | 规则引擎规则 |
| GET | `/dimensions` | 12 维维度定义 |
| GET/PUT | `/prompt` | 分析提示词 |
| POST | `/run` | 运行分析（规则/LLM） |
| GET | `/runs`、`/runs/{rid}` | 分析运行记录 |
| POST | `/items/{iid}/status` | 行动项状态更新 |

### 知识库 `/api/kb`
| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/import` | 批量导入（须在 `/{entity}` 前注册） |
| GET/POST | `/{entity}` | 实体列表 / 新增（entity ∈ keyword,bid,rank,competitor） |
| PUT/DELETE | `/{entity}/{eid}` | 更新 / 删除 |
| GET | `/{entity}/export` | 导出 CSV |
| GET | `/changes/log` | 变更记录 |

### 新品冷启动 `/api/launch`
| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/generate` | 生成冷启动广告架构 |
| GET | `/projects` | 项目列表 |
| GET/PUT/DELETE | `/projects/{pid}`、`/nodes/{nid}` | 项目 / 节点 查看与编辑 |
| GET | `/projects/{pid}/export` | 导出 Bulk Sheet |

### 多用户 `/api/admin`
| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/login` | 登录（演示） |
| GET/POST | `/users` | 用户列表 / 新建 |
| DELETE | `/users/{uid}` | 删除用户 |
| GET/POST | `/shops` | 店铺列表 / 新建 |
| GET | `/usage` | 调用用量 |
| GET | `/audit` | 审计日志 |

---

## 数据接入指南

1. 进入「数据投喂」页，选择店铺并上传报表文件（CSV/TSV/XLSX）。
2. 系统返回：识别出的报表类型 + 置信度、字段映射预览、行级异常数。
3. 若识别不准，可手动指定类型并调整字段映射（点列名下拉重新绑定）。
4. 选择写入模式（覆盖 / 追加 / 跳过重复），确认后入库。
5. 异常行可在「异常清单」查看并下载，不阻断其余数据入库。
6. 需要回滚时，在「数据版本」选择目标版本执行回滚。

> 演示数据：后端 `python seed_data.py` 会写入 5 份示例报表（SP 270 行含 5 处异常、ST 126 行、BR 60 行、ABA 15 行、BIZ 60 行），可直接体验 BI 与 AI 分析。

---

## 配置 AI 模型

1. 进入「AI 分析」→「模型配置」，填写：
   - **Endpoint**：OpenAI 兼容的 `/v1/chat/completions` 地址（如 `https://api.openai.com/v1`）。
   - **模型名**：如 `gpt-4o-mini`。
   - **API Key**：仅本地 XOR 混淆存储，界面以掩码显示。
2. 点击「测试」验证连通性。
3. 可选编辑提示词与规则权重。
4. 点击「运行分析」：有 Key 且可达 → 走 LLM；否则自动降级为内置规则引擎并提示。

---

## 测试

后端包含端到端冒烟测试（基于 FastAPI `TestClient`，覆盖接入→BI→分析→知识库→冷启动→多用户全流程，31 项断言）：

```bash
cd backend
pip install -r requirements.txt
python test_e2e.py
```

CI（`.github/workflows/ci.yml`）在每次 push/PR 自动运行：安装后端依赖 → 执行 `test_e2e.py` → 安装并构建前端。

---

## 部署与数据库切换

- 默认 SQLite（单文件 `backend/data/app.db`），零配置启动。
- 切换到 PostgreSQL：修改 `backend/app/db.py` 中的 `DATABASE_URL` 为
  `postgresql+psycopg://user:pass@host:5432/dbname`，并 `pip install psycopg[binary]`。
- 生产鉴权：将 `auth.py` 的 `X-Username` 头替换为 JWT/OAuth2，并在每个 router 的 `Depends(current_user)` 处校验。
- 前端构建产物 `frontend/dist` 由后端 `StaticFiles` 托管；也可改为独立静态托管 + 反向代理。

---

## 已知限制

- 报表类型覆盖 SP / SB / SD / 搜索词 / 业务报告 / ABA / 品牌指标；SB、SD 的专属维度（落地页、创意、标题、受众、商品定向 ASIN、投放位置）已完整解析落库，BI 可按广告格式 / 投放位置 / 定向下钻。
- 鉴权为 `X-Username` 请求头，仅用于演示多用户与权限隔离，生产需替换为 JWT/OAuth。
- 存储默认 SQLite，单文件便于启动；高并发/大数据量请切换到 PostgreSQL。
- 未接入 SP-API 定时同步，报表需手动上传（可后续用 `proboost`/卖家精灵等连接器补齐）。
- LLM 结论依赖模型返回质量，关键决策仍建议人工复核 `evidence`。
- **跨店聚合当前按 `campaign_id` 归并**：选中多个店铺时，若不同店铺存在相同 `campaign_id` 会被合并为同一行（按投放维度求和）。后续版本将支持按 `shop_id` 命名空间分组，避免跨店活动名相撞。

---

## 许可证与贡献

- 许可证：[MIT](./LICENSE) © 2026 Dragonhei
- 欢迎提 Issue / PR。本地开发遵循上方「快速开始」即可；提交前请确保 `python test_e2e.py` 与前端 `npm run build` 通过。
