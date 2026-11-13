from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AuditLog, Notification, Role, User, Vendor


def record(db: Session, actor: User | None, action: str, entity_type: str, entity_id: int | None,
           label: str | None, message: str) -> None:
    """Add an audit row. The caller commits."""
    db.add(AuditLog(
        actor_id=actor.id if actor else None, actor_name=actor.name if actor else "System",
        actor_role=actor.role.value if actor else None, action=action, entity_type=entity_type,
        entity_id=entity_id, entity_label=label, message=message[:400],
    ))


def vendor_users(db: Session, vendor: Vendor) -> list[User]:
    """Login accounts that belong to a vendor record (matched by email)."""
    if not vendor.email:
        return []
    return list(db.scalars(select(User).where(
        func.lower(User.email) == vendor.email.lower(), User.role == Role.vendor, User.is_active.is_(True))))


def staff_with_roles(db: Session, roles: tuple[Role, ...]) -> list[User]:
    return list(db.scalars(select(User).where(User.role.in_(roles), User.is_active.is_(True))))


def notify(db: Session, users: list[User], actor: User | None, kind: str, title: str, message: str,
           entity_type: str, entity_id: int | None, link: str | None) -> None:
    """Notify each user once. The person who caused the event is not told about their own action."""
    seen = {actor.id} if actor else set()
    for u in users:
        if u.id in seen:
            continue
        seen.add(u.id)
        db.add(Notification(user_id=u.id, kind=kind, title=title[:150], message=message[:400],
                            entity_type=entity_type, entity_id=entity_id, link=link))


def notify_rfq_vendors(db: Session, rfq, actor: User | None, kind: str, title: str, message: str) -> None:
    """Tell the login accounts of every vendor assigned to the RFQ."""
    people = []
    for rv in rfq.vendors:
        people += vendor_users(db, rv.vendor)
    notify(db, people, actor, kind, title, message, "rfq", rfq.id, f"/my-rfqs/{rfq.id}")