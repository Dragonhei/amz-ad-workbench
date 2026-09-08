"""把 samples/ 下的 5 份示例报表导入数据库，让首次打开就有数据可看。"""
import os
import sys

os.environ["KEEP_TMP"] = "1"      # 批量导入时保留临时文件，避免受限环境下删除失败中断流程

from fastapi.testclient import TestClient   # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.main import app          # noqa: E402

SAMPLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples")
FILES = [
    "sp_keyword_report.csv",
    "sp_search_term_report.csv",
    "business_report.csv",
    "aba_search_terms.csv",
    "brand_metrics_report.csv",
]
# 多店铺 / 多站点示例：同一份报表模板分别落入 3 个店铺，便于演示跨店汇总
SHOP_IDS = [1, 2, 3]


def main():
    c = TestClient(app)
    c.__enter__()
    for shop_id in SHOP_IDS:
        print(f"\n--- 店铺 {shop_id} ---")
        for f in FILES:
            path = os.path.join(SAMPLE, f)
            if not os.path.exists(path):
                print(f"  跳过（文件不存在）：{f}")
                continue
            with open(path, "rb") as fh:
                r = c.post("/api/ingest/preview", data={"shop_id": shop_id}, files={"file": (f, fh)})
            p = r.json()
            if not p.get("ok"):
                print(f"  识别失败：{f} → {p.get('message')}")
                continue
            r2 = c.post("/api/ingest/commit", json={
                "tmp_path": p["tmp_path"], "shop_id": shop_id, "report_type": p["report_type"],
                "mapping": p["mapping"], "strategy": "overwrite", "file_name": f})
            d = r2.json()
            print(f"  {f:34s} → {p['report_type']:4s} 入库 {d.get('row_ok')} 行 / "
                  f"异常 {d.get('row_err')} 行 / 期间 {d.get('period')}")
    print("示例数据导入完成（店铺 1/2/3）")


if __name__ == "__main__":
    main()
