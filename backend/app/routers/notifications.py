from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Notification, User
from app.schemas import NotificationOut, UnreadCountOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
def my_notifications(unread_only: bool = False, limit: int = Query(50, ge=1, le=200),
                     db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Always filtered by the logged-in user, so nobody can read another person's notifications."""
    query = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        query = query.where(Notification.is_read.is_(False))
    return db.scalars(query.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit)).all()


@router.get("/unread-count", response_model=UnreadCountOut)
def unread_count(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    n = db.scalar(select(func.count()).select_from(Notification)
                  .where(Notification.user_id == user.id, Notification.is_read.is_(False)))
    return {"count": n or 0}


@router.post("/read-all", response_model=UnreadCountOut)
def read_all(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.execute(update(Notification).where(Notification.user_id == user.id, Notification.is_read.is_(False))
               .values(is_read=True, read_at=datetime.now(timezone.utc)))
    db.commit()
    return {"count": 0}


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(notification_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != user.id:  # someone else's notification looks the same as a missing one
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")
    if not n.is_read:
        n.is_read = True
        n.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(n)
    return n