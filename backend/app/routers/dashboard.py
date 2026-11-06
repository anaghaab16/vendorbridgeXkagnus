from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Vendor, PurchaseOrder

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    total_vendors = db.query(Vendor).count()
    active_vendors = db.query(Vendor).filter(Vendor.status == "active").count()
    pending_vendors = db.query(Vendor).filter(
        Vendor.status == "pending").count()
    open_po_count = db.query(PurchaseOrder).filter(
        PurchaseOrder.status == "open").count()

    recent_orders = (
        db.query(PurchaseOrder)
        .order_by(PurchaseOrder.created_at.desc())
        .limit(5)
        .all()
    )

    return {
        "metrics": {
            "total_vendors": total_vendors,
            "active_vendors": active_vendors,
            "pending_vendors": pending_vendors,
            "open_purchase_orders": open_po_count,
        },
        "recent_orders": [
            {
                "id": po.id,
                "po_number": po.po_number,
                "vendor_name": po.vendor.name if po.vendor else "Unknown",
                "amount": po.total_amount,
                "status": po.status,
            }
            for po in recent_orders
        ]
    }
