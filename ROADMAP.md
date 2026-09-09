# 增强路线图 P1 / P2（设计稿 · 待确认）

> 目标：在现有六模块工作台上扩展 P1（高优先）与 P2（次优先）能力。
> 原则：复用现有七层数据模型，尽量扩展列而非新建表；所有功能带 `shop_id` 数据权限与时间维度；规则/告警可配置、可降级；前端沿用 AntD + ECharts。

## 现状基线（已实现，可直接复用）

- `Shop` 已有 `marketplace`(默认 US)、`currency`(默认 USD) 字段 → 多站点地基已具备。
- `FactAdPerf` 已有 `ad_format`(SP/SB/SD)、`level`、`targeting`、`match_type` → SB/SD 维度已留位。
- `KbRankTrack` / `KbCompetitor` 表已存在 → 排名追踪与竞品库后端已就绪，缺 UI 与自动抓取。
- `ActionItem` / `Evidence` 已存在 → 方案执行回填是在其之上加执行记录。
- 缺：库存事实表、`ActionExecution` 执行记录表、通知/评论相关表。

---

## P1（高优先）

### P1-1 多店铺多站点 ✅ 已完成
- **目标**：一个工作台管理多店铺、多 Amazon 站点（US/UK/DE/JP/CA/AU…），BI 可跨店汇总或按站点下钻。
- **数据模型**：`Shop` 已补 `timezone`(String, server_default)；种子数据补多店铺多站点示例（US/DE/UK，各带 marketplace/currency/timezone）；金额按 `shop.currency` 展示（不强求跨币换算）。
- **后端**：`metrics.aggregate/period_totals/date_range_of/daily_trend` 统一接受 `shop_ids`（int|list|None）；`auth.resolve_shop_ids` + `auth.my_shops` 提供权限感知的店铺解析；`/api/bi` 全部聚合接口支持 `shop_id` 列表 + `marketplace` 过滤；新增 `/api/bi/shops`（auth 感知，含 marketplace/currency/timezone）。`seed_data.py` 将示例报表灌入 1/2/3 三个店铺。
- **前端**：店铺切换器改为多选（留空=全部授权店铺），注入 `shopIds` 与 `currency` 到 Context；BI 顶部增加 `marketplace` 站点筛选；金额按币种格式化（`CUR_SYMBOL` 表）；Dashboard 同步币种。
- **验收**：e2e 已覆盖——3 店铺清单、跨店聚合花费 = 单店之和、marketplace 过滤仅留该站点、权限越界 403。工作量 **M**。
- **已知限制**：跨店聚合按 `campaign_id` 归并，不同店铺相同 `campaign_id` 会合并（后续按 `shop_id` 命名空间分组）。

### P1-2 SB / SD 全支持 ✅ 已完成
- **目标**：Sponsored Brands（品牌广告）与 Sponsored Display（展示型广告）报表完整解析、聚合与下钻。
- **数据模型**：`FactAdPerf` 新增 6 列 `landing_page_id`、`creative_id`、`headline`、`audience_id`、`placement`、`associated_asin`（SD 商品定向）；旧库经 `seed._ensure_schema` 自动 `ALTER TABLE` 补齐（与 P1-1 timezone 同机制）。
- **后端**：`parsers.detect_type` 增加 SB/SD 决定性指纹（Landing Page / Creative / Headline / Placement → SB；Advertised ASIN / Page Type / Matched Audience / Matched Target → SD），并扩充别名表与 SB/SD canonical 字段集；`metrics.aggregate` 支持 `ad_format` / `placement` / `targeting` 过滤与分组；`ingest.commit` 落库 6 个新列。
- **前端**：BI 顶部新增「广告格式」下拉（全部/SP/SB/SD），分组维度新增「广告格式 / 投放位置 / 定向」，金额按店铺币种渲染不变。
- **验收**：新增示例报表 `sb_keyword_report.csv` / `sd_product_report.csv` 随 3 店铺灌库；e2e 5c 节覆盖 SB/SD 自动识别、入库、按 `ad_format` 聚合同时含 SP/SB/SD、`ad_format=SB` 过滤、placement/targeting 下钻。全量 **45/45 通过**。
- **已知限制**：SB 与 SD 在 `FactAdPerf` 共用同一张表、以 `ad_format` 区分；跨格式聚合时相同 `campaign_id` 仍会归并（同 P1-1 的跨店命名空间问题，后续按 `shop_id+ad_format` 命名空间分组）。工作量 **L**（已完成）。

### P1-3 排名追踪与竞品库 ✅ 已完成
- **目标**：竞品 ASIN/品牌库可视化，排名随时间追踪，掉落预警。
- **数据模型**：`KbRankTrack` 增加 `marketplace`(默认 US)、`rank_source`(manual|aba|import) 两列与复合索引；旧库经 `seed._ensure_schema` 自动 `ALTER TABLE` 补齐。
- **后端**：排名列表接口（复用 `/api/kb/rank`）为最新一条记录附加 `delta_organic`（较 10 天内上次环比，正数=下跌）；新增 `GET /api/kb/rank/trend`（按 asin+term+marketplace 分组时间序列 + 掉落预警 `drops`）、`GET /api/kb/aba/terms`（ABA 高潜词）、`POST /api/kb/rank/from-aba`（一键加入追踪）；`rules.run_rules` 新增第 14 节排名掉落告警（较上周跌 ≥ 5 名 → `competitor` 维度 P1 结论，含证据）。
- **前端**：知识库页「排名追踪」增加 `marketplace` / `rank_source` 字段与「较上周」delta 列（红降绿升）；新增「排名趋势」Tab（ECharts 折线 + 掉落预警表），排名轴倒序；「从 ABA 添加」弹窗一键建追踪。
- **种子数据**：店铺 1/2/3 各写入 6 周排名历史（含 1 处明显掉落以演示预警）。
- **验收**：e2e 5e 节覆盖趋势序列、掉落预警、列表 delta、ABA 词获取与一键加入；全量 **59/59 通过**。工作量 **M**（已完成）。

### P1-4 规则可视化 DSL ✅ 已完成
- **目标**：用结构化、可拖选的「条件 → 动作」规则替代/增强裸 JSON 规则，非工程师可维护。
- **DSL 形态（最终实现）**：`WHEN <metric> <op> <threshold> [FOR <scope>] THEN [SUGGEST] <dimension> "<模板>" [WITH SEVERITY <high|mid|low>]`。
  - 示例：`WHEN acos > 40 FOR campaign THEN SUGGEST bid "活动「{scope}」ACOS 达 {value}%，建议下调竞价" WITH SEVERITY mid`
  - `<metric>`：统一指标口径（impressions/clicks/ctr/cpc/spend/orders/cvr/sales/acos/roas/tacos）；百分比指标按百分比数值比较（如 `ctr < 0.2` 表示 0.2%）。
  - `<scope>`：account（默认，整体汇总）/ campaign / keyword / adgroup / ad_format / placement / targeting，决定聚合粒度。
  - `<dimension>`：12 维分析维度之一；`<severity>`：high/mid/low → 结论优先级 P0/P1/P2。
  - 模板支持占位符：`{metric} {metric_code} {op} {op_sym} {threshold} {value} {scope} {dimension} {entities} {name}`。
- **数据模型**：`AnalysisRule` 增加 `dsl_text`（Text，存 DSL 原文）；结构化条件由 `dsl.parse_dsl` 实时解析得到（不另存冗余 JSON）。旧库经 `seed._ensure_schema` 自动 `ALTER TABLE` 补齐 `dsl_text` 列。
- **后端**：新增 `app/dsl.py`（`parse_dsl` / `validate_rule` / `check_dsl` / `evaluate_rule` / `dsl_meta`）；`rules.run_rules` 第 15 节加载启用且含有效 `dsl_text` 的规则并求值，命中即生成对应维度结论（带证据）；`routers/analysis.py` 新增 `GET /api/analysis/dsl/meta`、`GET /api/analysis/dsl/validate`、`POST /api/analysis/rules`、`DELETE /api/analysis/rules/{rid}`，并让 `GET/PUT /api/analysis/rules` 兼容读写 `dsl_text`。
- **前端**：分析页新增「自定义规则 (DSL)」Tab——表格展示现有规则（DSL 文本/启用开关/编辑/删除）+ 可视化构建器（选指标/运算符/阈值/作用域/维度/严重度 + 模板），实时拼装并预览 DSL，支持「校验语法」与「保存为规则/保存修改」；运行分析后命中结论自然出现在行动方案对应维度。
- **种子数据**：内置 2 条示例 DSL 规则（活动 ACOS 超阈值、关键词 CTR 偏低）演示。
- **验收**：e2e 6b 节覆盖 DSL meta、合法/非法 DSL 校验、`POST` 创建规则、运行分析断言该规则命中并产出对应维度结论（带证据）、`DELETE` 规则后列表移除；全量 **69/69 通过**（新增 10 项）。工作量 **L**（已完成）。

### P1-5 方案执行回填与效果复盘
- **目标**：把分析行动项标记为「已执行」并回填改动，复盘执行前后效果。
- **数据模型**：新增 `ActionExecution`(action_id, executed_at, before_snapshot JSON, after_snapshot JSON, change_note)；`ActionItem` 加 `executed` 标志。
- **后端**：`POST /api/analysis/items/{iid}/execute` 记录执行与前后快照；`GET /api/analysis/retro` 对比执行前后 N 天指标 lift（ACOS/CVR/花费/销售额）。
- **前端**：行动项「执行并回填」按钮；复盘前后对比图（执行日前后区间叠加）。
- **验收**：标记执行后能看到前后指标 diff 与提升幅度。工作量 **M**。

### P1-6 库存联动预警 ✅ 已完成
- **目标**：低库存 / 可售天数不足时联动广告预警（建议降预算或暂停）。
- **数据模型**：新增 `FactInventory`(shop_id, asin, date, sku, qty, inbound, daily_sales, days_of_cover)，含 `shop_id+date`、`shop_id+asin` 索引；旧库经 `Base.metadata.create_all` 自动建表。
- **后端**：`parsers.detect_type` 增加 INV 指纹（inbound / days of cover 决定性 +10；asin+可售且无广告指标 +5；文件名 inventory/inv_ 提示），字段别名与 canonical 集扩展；`ingest.commit` 落库 6 列；新增 `GET /api/inventory?shop_id=&marketplace=&threshold=` 返回每 ASIN 最新快照、可售天数、low_stock/advertised 标记与汇总；`rules.run_rules` 第 6 节改为逐 ASIN 计算可售天数，在投 ASIN 低库存 → P0 库存告警、其余 → P2，无库存报表时回退业务报告总量粗估。
- **前端**：新增「库存预警」页（ASIN 快照表 + 阈值可调 + 低库存红标）；工作台（Dashboard）增加库存告急告警条；AI 分析页在存在库存 P0 时显示横幅。
- **验收**：`samples/inventory_report.csv` 随 3 店铺灌库；e2e 5d 节覆盖 INV 识别、看板低库存汇总、在投告急 ASIN、阈值可调、分析库存 P0 告警。全量 **53/53 通过**。工作量 **M**（已完成）。

---

## P2（次优先）

### P2-1 SP-API 定时同步
- **目标**：定时从亚马逊 SP-API 拉取广告/业务报表，免手动上传。
- **依赖**：AWS 凭证（加密存储）+ SP-API（advertising/selling）。可借助已连接的 `linkfox-wb-amazon-sp-api` 连接器。
- **后端**：凭证管理（加密）、调度器（APScheduler）、增量同步、复用现有 `parsers` 映射。
- **工作量**：**L**（外部依赖重，建议放最后）。

### P2-2 多模型对比
- **目标**：同一份数据用多个 LLM 跑分析，并排对比结论。
- **后端**：`/api/analysis/run` 支持多 `provider_id`，存每模型 ActionItem 集。
- **前端**：对比视图（diff 高亮）。工作量 **M**。

### P2-3 告警推送
- **目标**：预警推送到邮件 / Webhook / 钉钉 / 企业微信 / Slack。
- **后端**：通知渠道配置 + 调度器，复用 P1 的告警产出。工作量 **M**。

### P2-4 协作评论
- **目标**：行动项 / 分析 / 活动下评论协作。
- **数据模型**：新增 `Comment`(entity_type, entity_id, user_id, text, created_at)。
- **后端**：`/api/comment` CRUD。
- **前端**：评论线程组件。工作量 **S/M**。

---

## 建议实施顺序

`P1-1 多店铺多站点`（地基）→ `P1-2 SB/SD 全支持`（数据完整）→ `P1-6 库存联动预警`（新数据）→ `P1-3 排名追踪与竞品库`（已有表补 UI）→ `P1-4 规则可视化 DSL`（分析力）→ `P1-5 方案执行回填与效果复盘`（闭环）→ `P2` 按依赖推进。

## 开放问题 / 假设（需你确认）

1. **跨站点金额**：是否按原币分别展示（不强制换算汇率）？建议原币展示，避免汇率维护。
2. **库存数据源**：P1 阶段先支持手动上传库存报表，SP-API 自动同步留到 P2-1。
3. **排名来源**：先支持手动录入 + ABA 词辅助建任务，暂不接实时排名抓取。
4. **时区**：报表日期以店铺 `timezone` 归一，避免跨站点日期错位。
