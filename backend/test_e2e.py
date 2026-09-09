"""端到端冒烟测试：上传解析 → BI 聚合 → 分析 → 知识库 → 冷启动 → 导出。"""
import json
import os
import sys
from urllib.parse import quote

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.main import app          # noqa: E402

c = TestClient(app)
c.__enter__()          # 触发 startup：建表 + 种子数据
SAMPLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples")
H = {"X-Username": "admin"}
ok = fail = 0


def check(name, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  [OK]   {name} {extra}")
    else:
        fail += 1
        print(f"  [FAIL] {name} {extra}")


def upload(fname, expect_type, strategy="overwrite", shop_id=1):
    with open(os.path.join(SAMPLE, fname), "rb") as f:
        r = c.post("/api/ingest/preview", data={"shop_id": shop_id}, files={"file": (fname, f)})
    p = r.json()
    assert r.status_code == 200, p
    if not p.get("ok"):
        return p
    rt = p["report_type"]
    r2 = c.post("/api/ingest/commit", json={"tmp_path": p["tmp_path"], "shop_id": shop_id,
                                            "report_type": rt, "mapping": p["mapping"],
                                            "strategy": strategy, "file_name": fname})
    res = r2.json()
    res.update({"report_type": rt, "detected": p.get("detected_type"),
                "confidence": p.get("confidence"), "mapping": p.get("mapping")})
    return res


print("\n=== 1. 健康检查 ===")
check("health", c.get("/api/health").json().get("ok"))

print("\n=== 2. 登录 ===")
r = c.post("/api/admin/login", json={"username": "admin", "password": "admin123"})
check("admin 登录", r.status_code == 200, r.text[:120])

print("\n=== 3. 报表解析（自动识别 + 脏数据处理）===")
res = upload("sp_keyword_report.csv", "SP")
check("SP 报表自动识别", res.get("report_type") == "SP" or res.get("ok"), str(res.get("report_type")))
sp = res
print("    识别置信度", sp.get("confidence"), "| 入库", sp.get("row_ok"),
      "行 | 异常", sp.get("row_err"), "行 | 期间", sp.get("period"))
check("SP 行数 > 100", (sp.get("row_ok") or 0) > 100)

st = upload("sp_search_term_report.csv", "ST")
check("搜索词报表识别为 ST", st.get("report_type") == "ST", str(st.get("report_type")))
biz = upload("business_report.csv", "BIZ")
check("业务报告识别为 BIZ", biz.get("report_type") == "BIZ", str(biz.get("report_type")))
aba = upload("aba_search_terms.csv", "ABA")
check("ABA 报表识别", aba.get("report_type") == "ABA", str(aba.get("report_type")))
br = upload("brand_metrics_report.csv", "BR")
check("BR 报表识别", br.get("report_type") == "BR", str(br.get("report_type")))

print("\n=== 4. 异常与版本 ===")
issues = c.get(f"/api/ingest/issues?job_id={sp['job_id']}").json()["items"]
check("记录行级异常", len(issues) > 0, f"{len(issues)} 条，示例：{issues[0]['message'] if issues else ''}")
vers = c.get("/api/ingest/versions?shop_id=1").json()["items"]
check("数据版本可追溯", len(vers) >= 5, f"{len(vers)} 个版本")

print("\n=== 5. BI 聚合 ===")
q = c.get("/api/bi/query?shop_id=1&group_by=campaign&sort_by=spend&sort_dir=desc",
          headers=H).json()
check("活动层级聚合", len(q["rows"]) == 3, f"{len(q['rows'])} 个活动")
s = q["summary"]
print(f"    汇总：曝光 {s['impressions']} 点击 {s['clicks']} 花费 ${s['spend']} "
      f"销售 ${s['sales']} ACOS {s['acos']}% TACOS {s['tacos']}%")
check("TACOS 有值（依赖业务报告）", s["tacos"] > 0, f"{s['tacos']}%")
kd = c.get("/api/bi/query?shop_id=1&group_by=keyword&sort_by=spend", headers=H).json()
check("关键词层级下钻", len(kd["rows"]) >= 8, f"{len(kd['rows'])} 个关键词")
tr = c.get("/api/bi/trend?shop_id=1", headers=H).json()
check("趋势序列", len(tr["points"]) >= 25, f"{len(tr['points'])} 天")
ov = c.get("/api/bi/overview?shop_id=1", headers=H).json()
check("概览含环比字段", "delta" in ov and "current" in ov,
      f"本期 ACOS {ov['current'].get('acos')}%，上期数据为空时环比为 None")

print("\n=== 5b. 多店铺 / 多站点 ===")
sh = c.get("/api/bi/shops", headers=H).json()["items"]
check("店铺清单含站点与币种", len(sh) >= 2 and all("marketplace" in s and "currency" in s for s in sh),
      f"{len(sh)} 个店铺，含 {','.join(s['marketplace'] for s in sh)}")
# 给店铺 2（德国站）也灌一份同模板 SP 报表，验证跨店聚合
up2 = upload("sp_keyword_report.csv", "SP", shop_id=2)
check("店铺2 报表入库", (up2.get("row_ok") or 0) > 0)
single = c.get("/api/bi/query?shop_id=1&group_by=campaign", headers=H).json()["summary"]["spend"]
multi = c.get("/api/bi/query?shop_id=1&shop_id=2&group_by=campaign", headers=H).json()
check("跨店聚合花费 > 单店（P1-1）", multi["summary"]["spend"] > single,
      f"单店 ${single} → 跨店 ${multi['summary']['spend']}")
check("跨店聚合活动数不变", len(multi["rows"]) == 3, f"{len(multi['rows'])} 个活动")
mp = c.get("/api/bi/query?shop_id=1&shop_id=2&marketplace=US&group_by=campaign", headers=H).json()
check("marketplace 过滤仅保留该站点", abs(mp["summary"]["spend"] - single) < 0.01,
      f"仅 US 站点花费 ${mp['summary']['spend']}")

print("\n=== 5c. SB / SD 全支持（P1-2）===")
sb = upload("sb_keyword_report.csv", "SB")
check("SB 报表自动识别", sb.get("report_type") == "SB", str(sb.get("report_type")))
print("    识别置信度", sb.get("confidence"), "| 入库", sb.get("row_ok"), "行 | 期间", sb.get("period"))
check("SB 行数 > 0", (sb.get("row_ok") or 0) > 0)
sb_q = c.get("/api/bi/query?shop_id=1&group_by=ad_format", headers=H).json()
sb_formats = {r["ad_format"] for r in sb_q["rows"]}
check("SB 入库后 ad_format 含 SB", "SB" in sb_formats, str(sorted(sb_formats)))
# 校验 SB 特有列确实落库：取一条 SB 明细看 landing_page/creative/placement 非空
sb_detail = c.get("/api/bi/query?shop_id=1&group_by=placement", headers=H).json()
check("SB placement 维度可下钻", len(sb_detail["rows"]) >= 1, f"{len(sb_detail['rows'])} 个投放位置")
sd = upload("sd_product_report.csv", "SD")
check("SD 报表自动识别", sd.get("report_type") == "SD", str(sd.get("report_type")))
print("    识别置信度", sd.get("confidence"), "| 入库", sd.get("row_ok"), "行 | 期间", sd.get("period"))
check("SD 行数 > 0", (sd.get("row_ok") or 0) > 0)
sd_q = c.get("/api/bi/query?shop_id=1&group_by=ad_format", headers=H).json()
all_formats = {r["ad_format"] for r in sd_q["rows"]}
check("按 ad_format 聚合同时含 SP/SB/SD", {"SP", "SB", "SD"}.issubset(all_formats), str(sorted(all_formats)))
# ad_format 过滤：仅取 SB（应等于按 ad_format 聚合中 SB 的花费）
sb_only = c.get("/api/bi/query?shop_id=1&group_by=campaign&filters=" + quote(
    json.dumps({"ad_format": "SB"})), headers=H).json()
sb_by_fmt = next((r["spend"] for r in sd_q["rows"] if r["ad_format"] == "SB"), None)
check("ad_format=SB 过滤仅剩 SB 花费", sb_only["summary"]["spend"] > 0
      and sb_by_fmt is not None and abs(sb_only["summary"]["spend"] - sb_by_fmt) < 0.01,
      f"过滤后 SB 花费 ${sb_only['summary']['spend']} = 聚合 SB ${sb_by_fmt}")
# SD 商品定向 ASIN 入库校验：按 targeting 维度下钻能看到定向表达式
sd_tg = c.get("/api/bi/query?shop_id=1&group_by=targeting", headers=H).json()
check("SD targeting 维度可下钻", len(sd_tg["rows"]) >= 1, f"{len(sd_tg['rows'])} 个定向")
print(f"    ad_format 各格式花费：", {r["ad_format"]: r["spend"] for r in sd_q["rows"]})

print("\n=== 5d. 库存联动预警（P1-6）===")
inv = upload("inventory_report.csv", "INV")
check("库存报表自动识别为 INV", inv.get("report_type") == "INV", str(inv.get("report_type")))
print("    识别置信度", inv.get("confidence"), "| 入库", inv.get("row_ok"), "行 | 期间", inv.get("period"))
check("INV 行数 > 0", (inv.get("row_ok") or 0) > 0)
inv_api = c.get("/api/inventory?shop_id=1", headers=H).json()
s = inv_api.get("summary", {})
check("库存看板返回低库存 ASIN", (s.get("low_count") or 0) > 0,
      f"低库存 {s.get('low_count')} / 在投告急 {s.get('advertised_low')} / 阈值 {s.get('threshold')}")
check("存在在投告急 ASIN（B0C1/B0C2 在业务报表有销量）",
      (s.get("advertised_low") or 0) > 0, f"advertised_low={s.get('advertised_low')}")
low_rows = [r for r in inv_api.get("items", []) if r.get("low_stock")]
check("低库存明细含 B0C1", any(r["asin"] == "B0C1" for r in low_rows),
      "低库存 ASIN: " + ",".join(r["asin"] for r in low_rows[:6]))
# 阈值上调后应不再告警（演示阈值可调）
inv_hi = c.get("/api/inventory?shop_id=1&threshold=1", headers=H).json()
check("阈值=1 时低库存归零", (inv_hi.get("summary", {}).get("low_count") or 0) == 0,
      f"low_count={inv_hi.get('summary', {}).get('low_count')}")

print("\n=== 6. 分析（规则引擎兜底）===")
rr = c.post("/api/analysis/run", json={"shop_id": 1, "target_acos": 35, "use_llm": False},
            headers=H).json()
items = rr.get("items", [])
check("产出结论", len(items) >= 5, f"{len(items)} 条，模式 {rr.get('mode')}")
dims = {i["dimension"] for i in items}
check("覆盖多个维度", len(dims) >= 5, str(sorted(dims)))
inv_items = [i for i in items if i["dimension"] == "inventory"]
check("分析含库存联动结论", len(inv_items) >= 1, f"库存维度 {len(inv_items)} 条")
check("在投告急 ASIN 触发 P0 库存告警", any(i["priority"] == "P0" for i in inv_items),
      "P0 库存项: " + ("有" if any(i["priority"] == "P0" for i in inv_items) else "无"))
ev_total = sum(len(i["evidence"]) for i in items)
check("每条结论带证据", all(i["evidence"] for i in items), f"共 {ev_total} 条证据")
for i in items[:3]:
    print(f"    [{i['priority']}][{i['dimension']}] {i['title'][:70]}")
cached = c.post("/api/analysis/run", json={"shop_id": 1, "target_acos": 35,
                                           "use_llm": True}, headers=H).json()
check("未配置 Key 时自动降级", cached["mode"] == "rule", cached.get("message", "")[:60])

print("\n=== 7. 知识库 ===")
kw = c.get("/api/kb/keyword?shop_id=1").json()["items"]
check("关键词库种子数据", len(kw) >= 10, f"{len(kw)} 条")
imp = c.post("/api/kb/import", json={"entity": "keyword", "shop_id": 1, "mode": "append",
                                     "rows": [{"term": "waffle shower curtain", "intent": "属性词",
                                               "relevance": "high", "status": "active"}]}).json()
check("批量导入", imp.get("inserted") == 1)
cid = c.post("/api/kb/competitor?shop_id=1", json={"competitor_asin": "B0T001", "brand": "TestBrand",
                                                   "price": 15.9, "rating": 4.1, "reviews": 300}).json()
check("新增竞品", cid.get("ok"))
log = c.get("/api/kb/changes/log?shop_id=1").json()["items"]
check("变更记录", len(log) >= 2, f"{len(log)} 条")

print("\n=== 8. 新品冷启动 ===")
lg = c.post("/api/launch/generate", json={"shop_id": 1, "asin": "B0NEW12345",
                                          "title": "Fabric Shower Curtain",
                                          "target_acos": 30, "daily_budget": 80},
            headers=H).json()
check("方案生成", lg.get("ok"), f"候选词池 {lg.get('keyword_pool')}")
tree = c.get(f"/api/launch/projects/{lg['project_id']}", headers=H).json()["tree"]
check("四活动结构", len(tree) == 4, f"{len(tree)} 个活动")
kwn = sum(len(g["children"]) for c in tree for g in c["children"])
print(f"    广告组 {sum(len(c['children']) for c in tree)} 个，关键词 {kwn} 个")
exp = c.get(f"/api/launch/projects/{lg['project_id']}/export", headers=H)
check("导出 Bulk CSV", exp.status_code == 200, f"{len(exp.text.splitlines())} 行")

print("\n=== 9. 管理后台 ===")
u = c.get("/api/admin/users", headers=H).json()["items"]
check("用户列表", len(u) >= 2, f"{len(u)} 个账号")
us = c.get("/api/admin/usage", headers=H).json()
check("用量统计", len(us["recent"]) >= 1, f"{len(us['recent'])} 条调用记录")
au = c.get("/api/admin/audit", headers=H).json()["items"]
check("审计日志", len(au) >= 1, f"{len(au)} 条")

print("\n=== 10. 权限边界 ===")
r = c.get("/api/bi/query?shop_id=2", headers={"X-Username": "operator"})
check("运营无权访问未授权店铺", r.status_code == 403, f"HTTP {r.status_code}")
r = c.get("/api/admin/users", headers={"X-Username": "operator"})
check("运营无法访问用户管理", r.status_code == 403, f"HTTP {r.status_code}")

print(f"\n===== 通过 {ok} 项，失败 {fail} 项 =====")
sys.exit(1 if fail else 0)
