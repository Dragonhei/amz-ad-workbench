"""协作评论：行动项 / 分析运行 / 知识库等实体的讨论线程（P2-4）。

统一 CRUD：
- GET    /api/comment?entity_type=&entity_id=   列出某实体的全部评论（含作者用户名、时间，按时间升序）
- POST   /api/comment                           发表评论（可带 parent_id 做一级回复）
- PUT    /api/comment/{cid}                     修改自己的评论
- DELETE /api/comment/{cid}                     删除自己的评论（级联删除其回复）
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import assert_shop_access, current_user
from ..db import get_db
from ..models import Comment, User

router = APIRouter(prefix="/api/comment", tags=["comment"])


class CommentIn(BaseModel):
    entity_type: str
    entity_id: int
    text: str
    shop_id: int = 0
    parent_id: int = None


def _serialize(c: Comment, db: Session) -> dict:
    user = db.query(User).get(c.user_id)
    return {
        "id": c.id,
        "entity_type": c.entity_type,
        "entity_id": c.entity_id,
        "shop_id": c.shop_id,
        "user_id": c.user_id,
        "username": user.username if user else "?",
        "full_name": user.full_name if user else "",
        "parent_id": c.parent_id,
        "text": c.text,
        "created_at": c.created_at.strftime("%Y-%m-%d %H:%M") if c.created_at else "",
    }


@router.get("")
def list_comments(entity_type: str, entity_id: int, db: Session = Depends(get_db),
                  u: User = Depends(current_user)):
    rows = (db.query(Comment)
            .filter(Comment.entity_type == entity_type, Comment.entity_id == entity_id)
            .order_by(Comment.created_at.asc()).all())
    return {"items": [_serialize(c, db) for c in rows]}


@router.post("")
def create_comment(body: CommentIn, db: Session = Depends(get_db), u: User = Depends(current_user)):
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(400, "评论内容不能为空")
    if body.shop_id:
        assert_shop_access(u, body.shop_id)
    c = Comment(entity_type=body.entity_type, entity_id=body.entity_id, shop_id=body.shop_id,
                user_id=u.id, parent_id=body.parent_id, text=text)
    db.add(c)
    db.commit()
    db.refresh(c)
    return {"ok": True, "id": c.id, "item": _serialize(c, db)}


@router.put("/{cid}")
def edit_comment(cid: int, body: dict, db: Session = Depends(get_db), u: User = Depends(current_user)):
    c = db.query(Comment).get(cid)
    if not c:
        raise HTTPException(404, "评论不存在")
    if c.user_id != u.id and u.role != "admin":
        raise HTTPException(403, "只能修改自己的评论")
    if body.get("text"):
        c.text = str(body["text"]).strip()
    db.commit()
    return {"ok": True}


@router.delete("/{cid}")
def delete_comment(cid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    c = db.query(Comment).get(cid)
    if not c:
        raise HTTPException(404, "评论不存在")
    if c.user_id != u.id and u.role != "admin":
        raise HTTPException(403, "只能删除自己的评论")
    db.query(Comment).filter(Comment.parent_id == cid).delete()
    db.delete(c)
    db.commit()
    return {"ok": True}
