# AI 广告分析工作台（Amazon Ads Workbench）

面向亚马逊卖家的广告分析工作台，Web 应用、界面中文。覆盖六大模块：数据投喂、LLM 分析、BI 看板、知识库、新品冷启动、多用户与配额。

## 一、快速启动

```bash
# 1) 后端（首次会自动建表 + 写入种子数据）
cd backend
pip install fastapi "uvicorn[standard]" sqlalchemy python-multipart openpyxl httpx
python seed_data.py        # 可选：导入 samples/ 下的 5 份示例报表
python run.py              # http://127.0.0.1:8000

# 2) 前端（开发模式，端口 5173，已配置 /api 代理到 8000）
cd frontend
npm install
npm run dev

# 或构建后由后端统一托管（访问 8000 即可）
cd frontend && npm run build && cd ../backend && python run.py
```

Windows 用户可直接双击根目录 `start.bat`。

内置账号：`admin / admin123`（管理员，全部数据权限）、`operator / 123456`（运营，仅授权店铺 1）。右上角可随时切换，用于验证数据权限差异。

## 二、目录结构

```
backend/
  app/
    models.py        # 七层数据模型（平台/接入/事实/派生/分析/知识库/冷启动）
    parsers.py       # 报表解析引擎：编码探测、表头定位、类型识别、字段映射、值清洗、行级校验
    metrics.py       # 统一指标口径与聚合查询
    rules.py         # 12 维维度定义、内置规则引擎（LLM 不可用时的兜底）
    llm.py           # OpenAI 兼容协议调用、重试、JSON 强约束、Key 混淆存储
    auth.py          # 极简鉴权与数据权限校验
    seed.py          # 种子数据
    routers/         # ingest / bi / analysis / kb / launch / admin
  samples/           # 示例报表（含人为注入的脏数据）
  test_e2e.py        # 端到端冒烟测试（31 项断言）
frontend/src/pages/  # Dashboard / Ingest / Analysis / Bi / Knowledge / Launch / Admin
```

## 三、模块要点

| 模块 | 说明 |
|---|---|
| 数据投喂 | 上传 CSV/TSV/XLSX → 自动识别类型与置信度 → 字段映射可手工调整 → 行级异常清单 → 覆盖/追加/跳过 → 数据版本可回滚 |
| AI 分析 | 模型可配（Endpoint / 模型名 / API Key），提示词与规则可编辑；输出 12 维结构化方案，**每条结论绑定 evidence（指标路径 + 数据快照）**，未配置 Key 或调用失败自动降级到内置规则引擎 |
| BI 看板 | 时间 / 活动 / 广告组 / 关键词 下钻，11 项指标筛选排序，趋势图与明细表点击联动 |
| 知识库 | 关键词库、CPC 竞价库、排名追踪、竞品库；增删改查 + CSV 批量导入导出 + 全量变更记录 |
| 新品冷启动 | 复用知识库与 ABA 词生成四活动架构（自动 / 精准 / 词组 / 商品定位），竞价取 CPC 库基准 × 匹配系数，可逐节点编辑并导出 Bulk Sheet |
| 多用户 | 管理员建号、分配店铺数据权限与 API 配额，记录调用量、Token、成本与审计日志 |

## 四、异常处理约定

- **报表格式错误**：识别失败时进入"手动指定类型 + 手动映射"流程；自动跳过前导说明行；表头走别名表 + 模糊匹配；`$`/`,`/`%`/负数/空值/多格式日期与 Excel 序列号均有清洗器；**行级异常不阻断入库**，异常行进 `parse_issue` 并可查看、可下载。
- **API 调用失败**：401/403 立即失败；超时/429/5xx 指数退避重试 3 次；输出非 JSON 时自动修复重试一次，仍失败则降级为规则引擎并明确提示；相同输入的运行结果按指纹缓存，避免重复计费。
- **性能**：事实表按 `shop_id + date` 建复合索引，BI 走服务端聚合与预聚合口径；默认限制行数与排序在服务端完成；LLM 只送聚合摘要与 Top N，不送原始明细。

## 五、已知限制（MVP 边界）

- 报表类型重点覆盖 SP / 搜索词 / BR / ABA / 业务报告；SB、SD 复用同一套 canonical 模型但未做专属字段（如品牌旗舰店落地页、受众定向）的解析规则。
- 鉴权为 `X-Username` 请求头，仅用于演示多用户与权限隔离，生产需替换为 JWT/OAuth。
- 存储默认 SQLite，单文件便于启动；切换到 PostgreSQL 只需修改 `app/db.py` 中的 `DATABASE_URL`。
- 未接入 SP-API 定时同步，报表需手动上传。
