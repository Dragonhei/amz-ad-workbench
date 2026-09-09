"""P2-3 告警推送：可插拔通知渠道 + 调度/触发 + 推送审计。

渠道类型：webhook / email / dingtalk / wecom / slack。
- webhook / dingtalk / wecom / slack：本质都是 Webhook POST（用户填入对应机器人 URL），
  真实外网会真正发出；`loopback://` 前缀用于本地测试，仅记录成功不实际请求。
- email：本地无 SMTP，统一标记为 simulated（detail 注明），生产可替换为真实邮件服务。
"""
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from urllib.error import URLError, HTTPError
from urllib.request import Request as _URequest, urlopen

from ..auth import assert_shop_access, current_user
from ..db import get_db
from ..models import AlertDispatch, NotificationChannel, Shop, User

router = APIRouter(prefix="/api/notify", tags=["notify"])

CHANNEL_TYPES = ["webhook", "email", "dingtalk", "wecom", "slack"]
HIGH_PRIORITIES = ("P0", "P1")


# ---------------------------------------------------------------- schemas
class ChannelIn(BaseModel):
    name: str
    chan_type: str
    shop_id: int = 1
    config: dict = {}
    enabled: Optional[bool] = True


class ChannelPatch(BaseModel):
    name: Optional[str] = None
    chan_type: Optional[str] = None
    config: Optional[dict] = None
    enabled: Optional[bool] = None


class TestIn(BaseModel):
    channel_id: int


# ---------------------------------------------------------------- 列表/增删改
@router.get("/channels")
def list_channels(db: Session = Depends(get_db), u: User = Depends(current_user)):
    q = db.query(NotificationChannel)
    if not u.is_admin:
        allowed = set(getattr(u, "shop_ids", []) or [])
        q = q.filter(NotificationChannel.shop_id.in_(allowed or [0]))
    rows = q.order_by(NotificationChannel.id.desc()).all()
    return {"items": [_ch(r) for r in rows]}


@router.post("/channels")
def create_channel(body: ChannelIn, db: Session = Depends(get_db), u: User = Depends(current_user)):
    assert_shop_access(u, body.shop_id)
    if body.chan_type not in CHANNEL_TYPES:
        raise HTTPException(400, f"不支持的渠道类型：{body.chan_type}")
    cfg = body.config or {}
    if body.chan_type != "email" and not cfg.get("url"):
        raise HTTPException(400, "非邮件渠道必须提供 url")
    ch = NotificationChannel(shop_id=body.shop_id, name=body.name, chan_type=body.chan_type,
                             config_json=json.dumps(cfg, ensure_ascii=False), enabled=body.enabled)
    db.add(ch)
    db.commit()
    return {"ok": True, "id": ch.id}


@router.put("/channels/{cid}")
def update_channel(cid: int, body: ChannelPatch, db: Session = Depends(get_db), u: User = Depends(current_user)):
    ch = db.query(NotificationChannel).get(cid)
    if not ch:
        raise HTTPException(404, "渠道不存在")
    assert_shop_access(u, ch.shop_id)
    if body.name is not None:
        ch.name = body.name
    if body.chan_type is not None:
        if body.chan_type not in CHANNEL_TYPES:
            raise HTTPException(400, f"不支持的渠道类型：{body.chan_type}")
        ch.chan_type = body.chan_type
    if body.config is not None:
        ch.config_json = json.dumps(body.config, ensure_ascii=False)
    if body.enabled is not None:
        ch.enabled = body.enabled
    db.commit()
    return {"ok": True}


@router.delete("/channels/{cid}")
def delete_channel(cid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    ch = db.query(NotificationChannel).get(cid)
    if not ch:
        raise HTTPException(404, "渠道不存在")
    assert_shop_access(u, ch.shop_id)
    db.delete(ch)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- 测试推送
@router.post("/test")
def test_channel(body: TestIn, db: Session = Depends(get_db), u: User = Depends(current_user)):
    ch = db.query(NotificationChannel).get(body.channel_id)
    if not ch:
        raise HTTPException(404, "渠道不存在")
    assert_shop_access(u, ch.shop_id)
    sample = [{"dimension": "test", "priority": "P1", "title": "【测试】广告投放告警",
               "detail": "这是一条来自「AI 广告分析工作台」的测试通知，用于验证告警推送链路是否正常。"}]
    status, detail = _send(ch, sample, ch.shop_id)
    rec = AlertDispatch(channel_id=ch.id, shop_id=ch.shop_id, priority_levels="P1",
                        item_count=1, status=status, detail=detail[:4000])
    db.add(rec)
    db.commit()
    return {"ok": True, "status": status, "detail": detail}


# ---------------------------------------------------------------- 推送历史
@router.get("/logs")
def list_logs(db: Session = Depends(get_db), u: User = Depends(current_user),
              shop_id: Optional[int] = None):
    q = db.query(AlertDispatch)
    if shop_id:
        assert_shop_access(u, shop_id)
        q = q.filter(AlertDispatch.shop_id == shop_id)
    rows = q.order_by(AlertDispatch.id.desc()).limit(200).all()
    return {"items": [{
        "id": r.id, "run_id": r.run_id, "channel_id": r.channel_id, "shop_id": r.shop_id,
        "priority_levels": r.priority_levels, "item_count": r.item_count,
        "status": r.status, "detail": r.detail, "sent_at": r.sent_at.isoformat() if r.sent_at else "",
    } for r in rows]}


# ---------------------------------------------------------------- 核心：把高优告警推到启用的渠道
def dispatch_alerts(db: Session, run_id: Optional[int], items: list, shop_id: int):
    """遍历该店铺启用的渠道，把 P0/P1 级告警推送到每个渠道并写审计记录。"""
    channels = db.query(NotificationChannel).filter_by(shop_id=shop_id, enabled=True).all()
    if not channels:
        return []
    alerts = [i for i in items if (getattr(i, "priority", "P2") or "P2") in HIGH_PRIORITIES]
    if not alerts:
        return []
    recs = []
    for ch in channels:
        status, detail = _send(ch, alerts, shop_id)
        rec = AlertDispatch(run_id=run_id, channel_id=ch.id, shop_id=shop_id,
                            priority_levels=",".join(HIGH_PRIORITIES), item_count=len(alerts),
                            status=status, detail=detail[:4000])
        db.add(rec)
        recs.append(rec)
    db.commit()
    return recs


# ---------------------------------------------------------------- 单个渠道发送（标准库实现，无第三方依赖）
def _send(ch: NotificationChannel, alerts: list, shop_id: int):
    cfg = {}
    try:
        cfg = json.loads(ch.config_json or "{}")
    except Exception:
        cfg = {}
    title = f"广告投放告警 · 店铺#{shop_id} · {len(alerts)} 条"
    lines = []
    for a in alerts:
        dim = getattr(a, "dimension", "")
        pri = getattr(a, "priority", "")
        t = getattr(a, "title", "")
        lines.append(f"[{pri}/{dim}] {t}")
    text = title + "\n" + "\n".join(lines)

    # 邮件：本地无 SMTP，标记 simulated
    if ch.chan_type == "email":
        return "simulated", "email 渠道为模拟发送（系统未配置 SMTP），请在生产环境接入真实邮件服务"

    url = (cfg.get("url") or "").strip()
    if not url:
        return "failed", "渠道未配置 url"

    # loopback:// 仅用于测试，不实际发请求
    if url.startswith("loopback://"):
        return "success", f"[loopback 模拟] 已就绪推送至 {ch.name}（{ch.chan_type}），内容：{text[:120]}"

    # 真实 Webhook POST（钉钉/企微/Slack/Generic 均为 URL 接收）
    try:
        payload = json.dumps({"msgtype": "text", "text": {"content": text}}, ensure_ascii=False).encode("utf-8")
        req = _URequest(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(req, timeout=8) as resp:
            body = resp.read().decode("utf-8", "ignore")[:300]
        return "success", f"HTTP {resp.status}：{body}"
    except HTTPError as e:
        return "failed", f"HTTP {e.code}：{e.read().decode('utf-8','ignore')[:200]}"
    except URLError as e:
        return "failed", f"连接失败：{e.reason}"
    except Exception as e:  # noqa: BLE001
        return "failed", f"发送异常：{str(e)[:200]}"


def _ch(r: NotificationChannel):
    return {"id": r.id, "shop_id": r.shop_id, "name": r.name, "chan_type": r.chan_type,
            "config": json.loads(r.config_json or "{}"), "enabled": r.enabled,
            "created_at": r.created_at.isoformat() if r.created_at else ""}
