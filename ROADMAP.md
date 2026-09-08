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

### P1-2 SB / SD 全支持
- **目标**：Sponsored Brands（品牌广告）与 Sponsored Display（展示型广告）报表完整解析、聚合与下钻。
- **数据模型**：`FactAdPerf` 增加列 `landing_page_id`、`creative_id`、`headline`、`audience_id`、`placement`、`associated_asin`（SD 商品定向）。
- **后端**：`parsers.detect_type` 增加 SB/SD 指纹（表头含 *Sponsored Brands / Sponsored Display / Targeting / Audience / Landing Page* 等）；字段映射别名表扩展；`/api/ingest/report-types` 补充 SB/SD 类型；BI 增加 `ad_format` / `placement` / `targeting` 下钻维度。
- **前端**：数据投喂类型选项补全；BI 增加「广告格式 / 投放位置」分组。
- **验收**：上传一份 SB + 一份 SD 报表能被正确识别、入库并按格式聚合。工作量 **L**。

### P1-3 排名追踪与竞品库
- **目标**：竞品 ASIN/品牌库可视化，排名随时间追踪，掉落预警。
- **现状**：`KbCompetitor` / `KbRankTrack` 已存在，需补 UI、自动建任务与图表。
- **数据模型**：`KbRankTrack` 增加 `marketplace`、`keyword`、`rank_source` 维度。
- **后端**：排名录入/批量导入接口（复用 `/api/kb`）；ABA 高频词可一键「加入排名追踪」；排名掉落告警规则（较上周跌 N 名触发）。
- **前端**：知识库页增加「竞品」「排名」Tab；排名趋势 ECharts 折线；掉落行高亮。
- **验收**：能看到竞品/关键词排名随时间变化曲线与预警。工作量 **M**。

### P1-4 规则可视化 DSL
- **目标**：用结构化、可拖选的「条件 → 动作」规则替代/增强裸 JSON 规则，非工程师可维护。
- **DSL 形态**：`WHEN <metric> <op> <threshold> FOR <scope> THEN suggest <dimension> "<模板>" WITH severity <high|mid|low>`。
- **数据模型**：`AnalysisRule` 增加 `dsl_text` 与结构化 `condition_json`（metric/op/threshold/scope/dimension/template/severity）。
- **后端**：DSL 解析器 + 校验器（转 ActionItem）；`/api/analysis/rules` 兼容新旧格式。
- **前端**：可视化规则构建器（选指标+运算符+阈值+作用维度+建议模板+严重度），实时预览 DSL 文本。
- **验收**：界面增删一条规则后，重新运行分析即体现该规则结论。工作量 **L**。

### P1-5 方案执行回填与效果复盘
- **目标**：把分析行动项标记为「已执行」并回填改动，复盘执行前后效果。
- **数据模型**：新增 `ActionExecution`(action_id, executed_at, before_snapshot JSON, after_snapshot JSON, change_note)；`ActionItem` 加 `executed` 标志。
- **后端**：`POST /api/analysis/items/{iid}/execute` 记录执行与前后快照；`GET /api/analysis/retro` 对比执行前后 N 天指标 lift（ACOS/CVR/花费/销售额）。
- **前端**：行动项「执行并回填」按钮；复盘前后对比图（执行日前后区间叠加）。
- **验收**：标记执行后能看到前后指标 diff 与提升幅度。工作量 **M**。

### P1-6 库存联动预警
- **目标**：低库存 / 可售天数不足时联动广告预警（建议降预算或暂停）。
- **数据模型**：新增 `FactInventory`(shop_id, asin, date, qty, inbound, days_of_cover)；或扩展 `FactListingDaily` 加库存列。
- **后端**：库存报表接入（`detect_type` 新类型）；分析告警规则（`days_of_cover < 阈值` 且该 ASIN 有花费 → 警告）。
- **前端**：库存 Widget + 预警徽标；分析页低库存提示。
- **验收**：上传库存表后，低库存 ASIN 在分析中被判为预警。工作量 **M**。

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
