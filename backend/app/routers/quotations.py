from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_roles
from app.models import (
    RFQ, Quotation, QuotationItem, QuotationStatus, RFQStatus, RFQVendor, Role, User,
)
from app.schemas import MyRFQDetailOut, MyRFQListOut, QuotationIn, QuotationOut
from app.services import (
    attachment_out, deadline_passed, get_rfq_or_404, is_assigned, item_out, quotation_out,
    vendor_for_user,
)

router = APIRouter(prefix="/my", tags=["vendor portal"])
# vendors never see drafts or cancelled RFQs
VISIBLE = (RFQStatus.sent, RFQStatus.closed)


def my_quotation(rfq: RFQ, vendor_id: int) -> Quotation | None:
    return next((q for q in rfq.quotations if q.vendor_id == vendor_id), None)


def visible_rfq(db: Session, rfq_id: int, vendor_id: int) -> RFQ:
    rfq = get_rfq_or_404(db, rfq_id)
    if rfq.status not in VISIBLE or not is_assigned(rfq, vendor_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "RFQ not found")
    return rfq


@router.get("/rfqs", response_model=list[MyRFQListOut])
def my_rfqs(db: Session = Depends(get_db), user: User = Depends(require_roles(Role.vendor))):
    vendor = vendor_for_user(db, user)
    rfqs = db.scalars(
        select(RFQ).join(RFQVendor, RFQVendor.rfq_id == RFQ.id)
        .where(RFQVendor.vendor_id == vendor.id, RFQ.status.in_(VISIBLE))
        .order_by(RFQ.deadline)
    ).all()
    out = []
    for r in rfqs:
        q = my_quotation(r, vendor.id)
        out.append({
            "id": r.id, "rfq_number": r.rfq_number, "title": r.title, "category": r.category, "deadline": r.deadline,
            "status": r.status, "deadline_passed": deadline_passed(r),
            "my_quotation_status": q.status if q else None,
        })
    return out


@router.get("/rfqs/{rfq_id}", response_model=MyRFQDetailOut)
def my_rfq(rfq_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.vendor))):
    vendor = vendor_for_user(db, user)
    rfq = visible_rfq(db, rfq_id, vendor.id)
    q = my_quotation(rfq, vendor.id)
    passed = deadline_passed(rfq)
    return {
        "id": rfq.id, "rfq_number": rfq.rfq_number, "title": rfq.title, "category": rfq.category, "deadline": rfq.deadline,
        "description": rfq.description, "status": rfq.status, "deadline_passed": passed,
        "can_edit": rfq.status == RFQStatus.sent and not passed, "vendor_name": vendor.name,
        "items": [item_out(i) for i in rfq.items],
        "attachments": [attachment_out(a) for a in rfq.attachments],
        "quotation": quotation_out(q) if q else None,
    }


@router.put("/rfqs/{rfq_id}/quotation", response_model=QuotationOut)
def save_quotation(rfq_id: int, data: QuotationIn, db: Session = Depends(get_db),
                   user: User = Depends(require_roles(Role.vendor))):
    vendor = vendor_for_user(db, user)
    rfq = visible_rfq(db, rfq_id, vendor.id)
    if rfq.status != RFQStatus.sent:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "This RFQ is closed for quotations")
    if deadline_passed(rfq):
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "The deadline has passed. Quotations can no longer be changed.")

    valid_ids = {i.id for i in rfq.items}
    sent_ids = [i.rfq_item_id for i in data.items]
    if len(set(sent_ids)) != len(sent_ids) or not set(sent_ids) <= valid_ids:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Prices must match the items of this RFQ, once each")

    q = my_quotation(rfq, vendor.id)
    if q is not None and q.is_selected:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Your quotation is now under review and can no longer be changed.")
    # a submitted quotation stays submitted; saving changes to it means submitting again
    submit = data.submit or (
        q is not None and q.status == QuotationStatus.submitted)
    if submit:
        if set(sent_ids) != valid_ids:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, "Enter a unit price for every item")
        if any(i.unit_price <= 0 for i in data.items):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, "Unit prices must be greater than zero")
        if data.delivery_days is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, "Enter the delivery time in days")

    if q is None:
        q = Quotation(rfq_id=rfq.id, vendor_id=vendor.id)
        q.rfq = rfq
        db.add(q)
    q.gst_percent = data.gst_percent
    q.delivery_days = data.delivery_days
    q.payment_terms = data.payment_terms
    q.notes = data.notes
    q.items = [QuotationItem(rfq_item_id=i.rfq_item_id,
                             unit_price=i.unit_price) for i in data.items]
    if submit:
        q.status = QuotationStatus.submitted
        q.submitted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(q)
    return quotation_out(q)
