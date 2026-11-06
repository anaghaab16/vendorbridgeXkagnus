from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_roles
from app.models import PurchaseOrder, Role, User
from app.schemas import POCreateIn, PODetailOut, POListOut
from app.workflow import can_see_po, generate_po, po_detail, po_list_row, vendor_scope

router = APIRouter(prefix="/purchase-orders", tags=["purchase orders"])
OFFICERS = (Role.admin, Role.procurement_officer)


@router.get("", response_model=list[POListOut])
def list_pos(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = select(PurchaseOrder).order_by(PurchaseOrder.created_at.desc())
    vendor_id = vendor_scope(db, user)  # a vendor user only ever gets its own
    if vendor_id is not None:
        query = query.where(PurchaseOrder.vendor_id == vendor_id)
    return [po_list_row(p) for p in db.scalars(query).all()]


@router.post("", response_model=PODetailOut, status_code=status.HTTP_201_CREATED)
def create_po(data: POCreateIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*OFFICERS))):
    """Create the PO for an approved quotation. Prices and totals come from the database."""
    return po_detail(generate_po(db, data.approval_id, user))


@router.get("/{po_id}", response_model=PODetailOut)
def read_po(po_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    po = db.get(PurchaseOrder, po_id)
    if po is None or not can_see_po(db, user, po):
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            "Purchase order not found")
    return po_detail(po)
