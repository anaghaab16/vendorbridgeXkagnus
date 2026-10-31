from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_roles
from app.models import Role, Vendor
from app.schemas import VendorIn, VendorOut

STAFF = (Role.admin, Role.manager, Role.procurement_officer)
router = APIRouter(prefix="/vendors", tags=["vendors"])


def get_or_404(db: Session, vendor_id: int) -> Vendor:
    vendor = db.get(Vendor, vendor_id)
    if vendor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vendor not found")
    return vendor


def check_email_free(db: Session, email: str | None, own_id: int | None = None):
    # a vendor user is matched to a vendor by email, so two vendors must not share one
    if not email:
        return
    other = db.scalar(select(Vendor).where(func.lower(
        Vendor.email) == email.lower(), Vendor.id != (own_id or 0)))
    if other:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"Email already used by vendor {other.name}")


@router.get("", response_model=list[VendorOut], dependencies=[Depends(require_roles(*STAFF))])
def list_vendors(db: Session = Depends(get_db)):
    return db.scalars(select(Vendor).order_by(Vendor.created_at.desc())).all()


@router.post("", response_model=VendorOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_roles(*STAFF))])
def create_vendor(data: VendorIn, db: Session = Depends(get_db)):
    check_email_free(db, data.email)
    vendor = Vendor(**data.model_dump())
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    return vendor


@router.get("/{vendor_id}", response_model=VendorOut, dependencies=[Depends(require_roles(*STAFF))])
def read_vendor(vendor_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, vendor_id)


@router.put("/{vendor_id}", response_model=VendorOut, dependencies=[Depends(require_roles(*STAFF))])
def update_vendor(vendor_id: int, data: VendorIn, db: Session = Depends(get_db)):
    vendor = get_or_404(db, vendor_id)
    check_email_free(db, data.email, vendor.id)
    for field, value in data.model_dump().items():
        setattr(vendor, field, value)
    db.commit()
    db.refresh(vendor)
    return vendor


# only admin and manager can delete
@router.delete("/{vendor_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_roles(Role.admin, Role.manager))])
def delete_vendor(vendor_id: int, db: Session = Depends(get_db)):
    vendor = get_or_404(db, vendor_id)
    try:
        db.delete(vendor)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "This vendor is used by an RFQ. Block it instead of deleting it.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
