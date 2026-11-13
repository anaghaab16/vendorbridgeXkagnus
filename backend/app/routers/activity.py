from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_roles
from app.models import AuditLog, Role, User
from app.schemas import ActivityPage

router = APIRouter(prefix="/activity", tags=["activity"])
FULL_ACCESS = (Role.admin, Role.manager)


@router.get("", response_model=ActivityPage)
def activity(entity_type: str | None = None, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
             db: Session = Depends(get_db),
             user: User = Depends(require_roles(Role.admin, Role.manager, Role.procurement_officer))):
    """The audit trail, newest first. Admins and managers see everything; an officer sees only their own actions.
    Vendors get a 403 from the role check. This router has no way to change or delete a record."""
    query = select(AuditLog)
    if user.role not in FULL_ACCESS:
        query = query.where(AuditLog.actor_id == user.id)
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit).offset(offset)).all()
    return {"items": items, "total": total}