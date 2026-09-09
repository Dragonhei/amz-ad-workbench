"""数据投喂：上传 → 预览（类型识别/字段映射/异常） → 入库（版本覆盖）。"""
import hashlib
import json
import os
import shutil
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import assert_shop_access, current_user
from ..db import BASE_DIR, get_db
from ..models import (DatasetVersion, FactAba, FactAdPerf, FactBrandMetric,
                      FactInventory, FactListingDaily, FactSearchTerm, IngestJob, ParseIssue,
                      SourceFile, User)
from ..parsers import (CANONICAL_FIELDS, REPORT_TYPES, build_mapping, detect_type,
                       parse_rows, read_table, REQUIRED_FIELDS)

router = APIRouter(prefix="/api/ingest", tags=["ingest"])
UPLOAD_DIR = os.path.join(BASE_DIR, "data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.get("/report-types")
def report_types():
    return {"types": [{"code": k, "name_zh": v} for k, v in REPORT_TYPES.items()],
            "canonical_fields": CANONICAL_FIELDS, "required_fields": REQUIRED_FIELDS}


@router.post("/preview")
async def preview(shop_id: int = Form(1), file: UploadFile = File(...),
                  report_type: str = Form(""), custom_mapping: str = Form(""),
                  db: Session = Depends(get_db), u: User = Depends(current_user)):
    assert_shop_access(u, shop_id)
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".csv", ".txt", ".tsv", ".xlsx", ".xlsm", ".xls"):
        raise HTTPException(400, f"不支持的文件类型 {ext}，仅支持 CSV / TSV / XLSX")
    tmp = os.path.join(UPLOAD_DIR, f"tmp_{os.getpid()}_{hashlib.md5(file.filename.encode()).hexdigest()[:8]}{ext}")
    with open(tmp, "wb") as f:
        shutil.copyfileobj(file.file, f)
    size = os.path.getsize(tmp)
    if size == 0:
        os.remove(tmp)
        raise HTTPException(400, "文件为空")
    try:
        headers, body, encoding, issues, _ = read_table(tmp)
    except Exception as e:                                   # noqa: BLE001
        os.remove(tmp)
        raise HTTPException(400, f"文件读取失败：{type(e).__name__}: {e}")

    if not headers:
        os.remove(tmp)
        raise HTTPException(400, "未找到有效表头，请检查文件是否为广告报表")

    detected, conf, scores = detect_type(headers, file.filename or "")
    final_type = report_type or detected
    if not final_type:
        return {"ok": False, "need_manual_type": True, "file_name": file.filename,
                "headers": headers, "scores": scores, "tmp_path": tmp,
                "message": "无法自动识别报表类型，请在下方手动选择类型并指定字段映射",
                "types": [{"code": k, "name_zh": v} for k, v in REPORT_TYPES.items()]}
    custom = {}
    if custom_mapping:
        try:
            custom = json.loads(custom_mapping)
        except ValueError:
            custom = {}
    mapping = build_mapping(headers, final_type, custom)
    sample_body = body[:300]
    records, row_issues, stats = parse_rows(sample_body, headers, mapping, final_type)
    missing = [f for f in REQUIRED_FIELDS.get(final_type, []) if f not in mapping]
    all_issues = issues + row_issues
    return {
        "ok": True, "tmp_path": tmp, "file_name": file.filename, "size": size,
        "encoding": encoding, "headers": headers,
        "detected_type": detected, "report_type": final_type, "confidence": conf, "scores": scores,
        "mapping": mapping, "missing_required": missing,
        "unmapped": [f for f in CANONICAL_FIELDS.get(final_type, []) if f not in mapping],
        "sample": records[:6], "issues": all_issues[:50], "issue_count": len(all_issues),
        "row_total": len(body), "preview_ok": stats["row_ok"], "preview_err": stats["row_err"],
        "types": [{"code": k, "name_zh": v} for k, v in REPORT_TYPES.items()],
    }


class CommitIn(BaseModel):
    tmp_path: str
    shop_id: int = 1
    report_type: str
    mapping: dict
    strategy: str = "append"          # append | overwrite | skip
    file_name: str = ""


def _clear_range(db, shop_id, report_type, d1, d2):
    if not d1 or not d2:
        return 0
    if report_type in ("SP", "SB", "SD"):
        n = db.query(FactAdPerf).filter(FactAdPerf.shop_id == shop_id,
                                        FactAdPerf.date >= d1, FactAdPerf.date <= d2,
                                        FactAdPerf.ad_format == report_type).delete()
    elif report_type == "ST":
        n = db.query(FactSearchTerm).filter(FactSearchTerm.shop_id == shop_id,
                                            FactSearchTerm.date >= d1,
                                            FactSearchTerm.date <= d2).delete()
    elif report_type == "BR":
        n = db.query(FactBrandMetric).filter(FactBrandMetric.shop_id == shop_id,
                                             FactBrandMetric.date >= d1,
                                             FactBrandMetric.date <= d2).delete()
    elif report_type == "ABA":
        n = db.query(FactAba).filter(FactAba.shop_id == shop_id,
                                     FactAba.week_start >= d1, FactAba.week_start <= d2).delete()
    elif report_type == "BIZ":
        n = db.query(FactListingDaily).filter(FactListingDaily.shop_id == shop_id,
                                              FactListingDaily.date >= d1,
                                              FactListingDaily.date <= d2).delete()
    elif report_type == "INV":
        n = db.query(FactInventory).filter(FactInventory.shop_id == shop_id,
                                           FactInventory.date >= d1,
                                           FactInventory.date <= d2).delete()
    else:
        n = 0
    return n


@router.post("/commit")
def commit(payload: CommitIn, db: Session = Depends(get_db), u: User = Depends(current_user)):
    assert_shop_access(u, payload.shop_id)
    tmp = payload.tmp_path
    if not os.path.exists(tmp):
        raise HTTPException(400, "预览已过期，请重新上传文件")
    with open(tmp, "rb") as f:
        raw = f.read()
    file_hash = hashlib.sha256(raw).hexdigest()
    dup = db.query(SourceFile).filter(SourceFile.file_hash == file_hash,
                                      SourceFile.shop_id == payload.shop_id).first()
    if dup and payload.strategy == "skip":
        raise HTTPException(409, f"该文件已上传过（{dup.file_name}，{dup.created_at:%Y-%m-%d %H:%M}），请选择覆盖或追加")

    headers, body, _enc, read_issues, _ = read_table(tmp)
    records, issues, stats = parse_rows(body, headers, payload.mapping, payload.report_type)
    blocking = [i for i in issues if i["severity"] == "blocking"]
    if blocking:
        raise HTTPException(400, "；".join(i["message"] for i in blocking))
    if not records:
        raise HTTPException(400, "没有可入库的有效数据行，请检查字段映射")

    store_name = f"{file_hash[:16]}_{os.path.basename(tmp)}"
    store_path = os.path.join(UPLOAD_DIR, store_name)
    shutil.copyfile(tmp, store_path)
    sf = SourceFile(shop_id=payload.shop_id, file_name=payload.file_name or os.path.basename(tmp),
                    file_hash=file_hash, size=len(raw), storage_path=store_path, uploader=u.username)
    db.add(sf)
    db.flush()

    dates = [r["date"] for r in records if r.get("date")]
    dates = dates or [r.get("week_start") for r in records if r.get("week_start")]
    d1, d2 = (min(dates), max(dates)) if dates else (date.today(), date.today())

    # 版本与覆盖策略
    exist = db.query(DatasetVersion).filter(
        DatasetVersion.shop_id == payload.shop_id,
        DatasetVersion.report_type == payload.report_type,
        DatasetVersion.period_start == d1, DatasetVersion.period_end == d2,
        DatasetVersion.is_active.is_(True)).all()
    replaced = 0
    if exist:
        if payload.strategy == "skip":
            raise HTTPException(409, f"{payload.report_type} 在 {d1} ~ {d2} 已有数据版本，请选择覆盖或追加")
        if payload.strategy == "overwrite":
            replaced = _clear_range(db, payload.shop_id, payload.report_type, d1, d2)
            for e in exist:
                e.is_active = False

    job = IngestJob(source_file_id=sf.id, shop_id=payload.shop_id, report_type=payload.report_type,
                    detected_type=payload.report_type, date_start=d1, date_end=d2,
                    row_total=stats["row_total"], row_ok=stats["row_ok"], row_err=stats["row_err"],
                    status="success" if stats["row_err"] == 0 else "partial",
                    strategy=payload.strategy, operator=u.username,
                    message=f"覆盖 {replaced} 行旧数据" if replaced else "")
    db.add(job)
    db.flush()

    ver = DatasetVersion(shop_id=payload.shop_id, report_type=payload.report_type,
                         period_start=d1, period_end=d2, job_id=job.id,
                         row_count=stats["row_ok"], is_active=True)
    db.add(ver)
    db.flush()

    objs = []
    rt = payload.report_type
    for r in records:
        if rt in ("SP", "SB", "SD"):
            kw = r.get("keyword", "")
            ag = r.get("adgroup_name", "")
            level = "keyword" if kw else ("adgroup" if ag else "campaign")
            objs.append(FactAdPerf(
                shop_id=payload.shop_id, date=r["date"], ad_format=rt, level=level,
                campaign_id=r.get("campaign_id", ""), campaign_name=r.get("campaign_name", "") or "(未命名活动)",
                adgroup_id=r.get("adgroup_id", ""), adgroup_name=ag,
                keyword_text=kw, match_type=r.get("match_type", ""), targeting=r.get("targeting", ""),
                landing_page_id=str(r.get("landing_page_id") or ""),
                creative_id=str(r.get("creative_id") or ""),
                headline=str(r.get("headline") or ""),
                audience_id=str(r.get("audience_id") or ""),
                placement=str(r.get("placement") or ""),
                associated_asin=str(r.get("associated_asin") or ""),
                impressions=int(r.get("impressions", 0)), clicks=int(r.get("clicks", 0)),
                spend=float(r.get("spend", 0)), orders=int(r.get("orders", 0)),
                units=int(r.get("units", 0)), sales=float(r.get("sales", 0)), version_id=ver.id))
        elif rt == "ST":
            objs.append(FactSearchTerm(
                shop_id=payload.shop_id, date=r["date"], campaign_id=r.get("campaign_id", ""),
                campaign_name=r.get("campaign_name", ""), adgroup_id=r.get("adgroup_id", ""),
                adgroup_name=r.get("adgroup_name", ""), search_term=r.get("search_term", ""),
                match_type=r.get("match_type", ""), impressions=int(r.get("impressions", 0)),
                clicks=int(r.get("clicks", 0)), spend=float(r.get("spend", 0)),
                orders=int(r.get("orders", 0)), sales=float(r.get("sales", 0)), version_id=ver.id))
        elif rt == "BR":
            objs.append(FactBrandMetric(
                shop_id=payload.shop_id, date=r["date"], asin=r.get("asin", ""),
                brand_search_volume=int(r.get("brand_search_volume", 0)),
                new_to_brand_orders=int(r.get("new_to_brand_orders", 0)),
                new_to_brand_pct=float(r.get("new_to_brand_pct", 0)),
                repeat_purchase_pct=float(r.get("repeat_purchase_pct", 0)), version_id=ver.id))
        elif rt == "ABA":
            objs.append(FactAba(
                shop_id=payload.shop_id, week_start=r.get("week_start") or r.get("date"),
                search_term=r.get("search_term", ""), search_rank=int(r.get("search_rank", 0)),
                top3_click_share=float(r.get("top3_click_share", 0)),
                top3_conv_share=float(r.get("top3_conv_share", 0)), version_id=ver.id))
        elif rt == "BIZ":
            objs.append(FactListingDaily(
                shop_id=payload.shop_id, date=r["date"], asin=r.get("asin", ""),
                sessions=int(r.get("sessions", 0)), page_views=int(r.get("page_views", 0)),
                units=int(r.get("units", 0)), orders=int(r.get("orders", 0)),
                total_sales=float(r.get("total_sales", 0)), inventory=int(r.get("inventory", 0)),
                version_id=ver.id))
        elif rt == "INV":
            objs.append(FactInventory(
                shop_id=payload.shop_id, date=r["date"], asin=r.get("asin", ""),
                sku=r.get("sku", ""), qty=int(r.get("qty", 0)), inbound=int(r.get("inbound", 0)),
                daily_sales=float(r.get("daily_sales", 0)),
                days_of_cover=float(r.get("days_of_cover", 0)), version_id=ver.id))
    for i in issues:
        db.add(ParseIssue(job_id=job.id, row_no=i["row_no"], severity=i["severity"],
                          column_name=i.get("column_name", ""), raw_value=str(i.get("raw_value", ""))[:200],
                          message=i["message"]))
    db.bulk_save_objects(objs)
    db.commit()
    if not os.environ.get("KEEP_TMP"):
        try:
            os.remove(tmp)
        except OSError:
            pass
    return {"ok": True, "job_id": job.id, "version_id": ver.id, "file_id": sf.id,
            "row_ok": stats["row_ok"], "row_err": stats["row_err"], "replaced": replaced,
            "period": [str(d1), str(d2)], "issues": issues[:50], "issue_count": len(issues)}


@router.get("/jobs")
def jobs(shop_id: int = 1, limit: int = 50, db: Session = Depends(get_db), u: User = Depends(current_user)):
    rows = (db.query(IngestJob).filter(IngestJob.shop_id == shop_id)
            .order_by(IngestJob.id.desc()).limit(limit).all())
    out = []
    for j in rows:
        sf = db.query(SourceFile).get(j.source_file_id)
        out.append({"id": j.id, "report_type": j.report_type,
                    "report_type_name": REPORT_TYPES.get(j.report_type, j.report_type),
                    "file_name": sf.file_name if sf else "", "date_start": str(j.date_start),
                    "date_end": str(j.date_end), "row_total": j.row_total, "row_ok": j.row_ok,
                    "row_err": j.row_err, "status": j.status, "strategy": j.strategy,
                    "operator": j.operator, "message": j.message,
                    "created_at": j.created_at.strftime("%Y-%m-%d %H:%M")})
    return {"items": out}


@router.get("/issues")
def issues(job_id: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    rows = (db.query(ParseIssue).filter(ParseIssue.job_id == job_id)
            .order_by(ParseIssue.id).limit(500).all())
    return {"items": [{"row_no": r.row_no, "severity": r.severity, "column": r.column_name,
                       "raw_value": r.raw_value, "message": r.message} for r in rows]}


@router.get("/versions")
def versions(shop_id: int = 1, db: Session = Depends(get_db), u: User = Depends(current_user)):
    rows = (db.query(DatasetVersion).filter(DatasetVersion.shop_id == shop_id)
            .order_by(DatasetVersion.id.desc()).limit(100).all())
    return {"items": [{"id": r.id, "report_type": r.report_type,
                       "report_type_name": REPORT_TYPES.get(r.report_type, r.report_type),
                       "period_start": str(r.period_start), "period_end": str(r.period_end),
                       "row_count": r.row_count, "is_active": r.is_active,
                       "created_at": r.created_at.strftime("%Y-%m-%d %H:%M")} for r in rows]}


@router.post("/rollback/{version_id}")
def rollback(version_id: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    v = db.query(DatasetVersion).get(version_id)
    if not v:
        raise HTTPException(404, "版本不存在")
    for other in db.query(DatasetVersion).filter(
            DatasetVersion.shop_id == v.shop_id, DatasetVersion.report_type == v.report_type,
            DatasetVersion.period_start == v.period_start,
            DatasetVersion.period_end == v.period_end).all():
        other.is_active = (other.id == version_id)
    db.commit()
    return {"ok": True, "message": f"已回滚到版本 #{version_id}，请重新查询 BI 看板"}
