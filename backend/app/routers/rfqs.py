import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_roles
from app.models import (
    RFQ, Quotation, QuotationStatus, RFQAttachment, RFQLineItem, RFQStatus, RFQVendor, Role, User,
    Vendor, VendorStatus,
)
from app.schemas import (
    AttachmentOut, CompareOut, RFQDetailOut, RFQIn, RFQListOut, RFQStatusIn, SelectIn,
)
from app.services import (
    attachment_out, build_comparison, get_rfq_or_404, is_assigned, rfq_detail, rfq_summary, vendor_for_user,
)

# can read RFQs and compare quotations
STAFF = (Role.admin, Role.manager, Role.procurement_officer)
OFFICERS = (Role.admin, Role.procurement_officer)  # can create and manage RFQs
router = APIRouter(prefix="/rfqs", tags=["rfqs"])

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"  # backend/uploads
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_FILES_PER_RFQ = 5
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg",
                      ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt"}

# allowed status changes
TRANSITIONS = {
    RFQStatus.draft: {RFQStatus.sent, RFQStatus.cancelled},
    RFQStatus.sent: {RFQStatus.closed, RFQStatus.cancelled},
}


def load_vendors(db: Session, vendor_ids: list[int]) -> list[Vendor]:
    if not vendor_ids:
        return []
    vendors = db.scalars(select(Vendor).where(Vendor.id.in_(vendor_ids))).all()
    if len(vendors) != len(vendor_ids):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "One or more vendors were not found")
    blocked = [v.name for v in vendors if v.status == VendorStatus.blocked]
    if blocked:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            f"Blocked vendors cannot be assigned: {', '.join(blocked)}")
    return vendors


@router.get("", response_model=list[RFQListOut], dependencies=[Depends(require_roles(*STAFF))])
def list_rfqs(db: Session = Depends(get_db)):
    rfqs = db.scalars(select(RFQ).order_by(RFQ.created_at.desc())).all()
    return [rfq_summary(r) for r in rfqs]


@router.post("", response_model=RFQDetailOut, status_code=status.HTTP_201_CREATED)
def create_rfq(data: RFQIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*OFFICERS))):
    if data.deadline < date.today():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Deadline cannot be in the past")
    vendors = load_vendors(db, data.vendor_ids)
    if data.send and not vendors:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Choose at least one vendor before sending")
    rfq = RFQ(
        title=data.title.strip(), category=data.category.strip(), deadline=data.deadline,
        description=data.description, created_by=user.id,
        status=RFQStatus.sent if data.send else RFQStatus.draft,
    )
    rfq.items = [RFQLineItem(item_name=i.item_name.strip(
    ), quantity=i.quantity, unit=i.unit.strip()) for i in data.items]
    rfq.vendors = [RFQVendor(vendor_id=v.id) for v in vendors]
    db.add(rfq)
    db.flush()  # gives the RFQ its id
    rfq.rfq_number = f"RFQ-{date.today().year}-{rfq.id:04d}"
    db.commit()
    db.refresh(rfq)
    return rfq_detail(rfq)


@router.get("/{rfq_id}", response_model=RFQDetailOut, dependencies=[Depends(require_roles(*STAFF))])
def read_rfq(rfq_id: int, db: Session = Depends(get_db)):
    return rfq_detail(get_rfq_or_404(db, rfq_id))


@router.patch("/{rfq_id}/status", response_model=RFQDetailOut, dependencies=[Depends(require_roles(*OFFICERS))])
def change_status(rfq_id: int, data: RFQStatusIn, db: Session = Depends(get_db)):
    rfq = get_rfq_or_404(db, rfq_id)
    if data.status not in TRANSITIONS.get(rfq.status, set()):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"A {rfq.status.value} RFQ cannot be changed to {data.status.value}")
    if data.status == RFQStatus.sent:
        if not rfq.vendors:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                "Assign at least one vendor before sending")
        if rfq.deadline < date.today():
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                "The deadline has passed. Create a new RFQ with a later deadline.")
    rfq.status = data.status
    db.commit()
    db.refresh(rfq)
    return rfq_detail(rfq)


@router.delete("/{rfq_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_roles(*OFFICERS))])
def delete_rfq(rfq_id: int, db: Session = Depends(get_db)):
    rfq = get_rfq_or_404(db, rfq_id)
    if rfq.status != RFQStatus.draft:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Only draft RFQs can be deleted. Cancel it instead.")
    stored = [a.stored_name for a in rfq.attachments]
    db.delete(rfq)
    db.commit()
    for name in stored:
        (UPLOAD_DIR / name).unlink(missing_ok=True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------ attachments

@router.post("/{rfq_id}/attachments", response_model=AttachmentOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_roles(*OFFICERS))])
def upload_attachment(rfq_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    rfq = get_rfq_or_404(db, rfq_id)
    if rfq.status not in (RFQStatus.draft, RFQStatus.sent):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Files can only be added to draft or sent RFQs")
    if len(rfq.attachments) >= MAX_FILES_PER_RFQ:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            f"An RFQ can have at most {MAX_FILES_PER_RFQ} files")
    display_name = Path(file.filename or "file").name[:200]
    ext = Path(display_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            f"File type {ext or '(none)'} is not allowed")
    content = file.file.read(MAX_FILE_BYTES + 1)
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File is larger than 5 MB")
    if not content:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "File is empty")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored = uuid.uuid4().hex + ext
    (UPLOAD_DIR / stored).write_bytes(content)
    att = RFQAttachment(rfq_id=rfq.id, file_name=display_name,
                        stored_name=stored, size=len(content))
    db.add(att)
    db.commit()
    db.refresh(att)
    return attachment_out(att)


@router.get("/{rfq_id}/attachments/{attachment_id}")
def download_attachment(rfq_id: int, attachment_id: int, db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)):
    rfq = get_rfq_or_404(db, rfq_id)
    if user.role == Role.vendor:
        vendor = vendor_for_user(db, user)
        if not is_assigned(rfq, vendor.id) or rfq.status not in (RFQStatus.sent, RFQStatus.closed):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    elif user.role not in STAFF:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "You do not have access")
    att = next((a for a in rfq.attachments if a.id == attachment_id), None)
    path = UPLOAD_DIR / att.stored_name if att else None
    if att is None or not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    return FileResponse(path, filename=att.file_name)


# ------------------------------------------------------------- comparison

@router.get("/{rfq_id}/comparison", response_model=CompareOut, dependencies=[Depends(require_roles(*STAFF))])
def compare(rfq_id: int, db: Session = Depends(get_db)):
    return build_comparison(get_rfq_or_404(db, rfq_id))


@router.put("/{rfq_id}/selected-quotation", response_model=CompareOut, dependencies=[Depends(require_roles(*OFFICERS))])
def select_quotation(rfq_id: int, data: SelectIn, db: Session = Depends(get_db)):
    """Mark one submitted quotation as the selected one. Week 3's approval workflow starts from it."""
    rfq = get_rfq_or_404(db, rfq_id)
    if rfq.status not in (RFQStatus.sent, RFQStatus.closed):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Quotations can only be selected on a sent or closed RFQ")
    target = None
    if data.quotation_id is not None:
        target = next((q for q in rfq.quotations if q.id ==
                      data.quotation_id), None)
        if target is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                "That quotation does not belong to this RFQ")
        if target.status != QuotationStatus.submitted:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                "Only submitted quotations can be selected")
    for q in rfq.quotations:
        q.is_selected = False
        q.selected_at = None
    db.flush()  # clear the old choice first so only one row is ever selected
    if target is not None:
        target.is_selected = True
        target.selected_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(rfq)
    return build_comparison(rfq)
