from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_roles
from app.models import ApprovalRequest, ApprovalStatus, Role, User
from app.schemas import ApprovalDetailOut, ApprovalListOut, ApprovalSubmitIn, DecisionIn
from app.workflow import (
    APPROVER_ROLES, STAFF_ROLES, approval_detail, approval_list_row, decide, submit_for_approval,
)

router = APIRouter(prefix="/approvals", tags=["approvals"])
OFFICERS = (Role.admin, Role.procurement_officer)


def load(db: Session, approval_id: int) -> ApprovalRequest:
    req = db.get(ApprovalRequest, approval_id)
    if req is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            "Approval request not found")
    return req


@router.get("", response_model=list[ApprovalListOut])
def list_approvals(db: Session = Depends(get_db), user: User = Depends(require_roles(*STAFF_ROLES)),
                   status_filter: ApprovalStatus | None = None):
    query = select(ApprovalRequest).order_by(ApprovalRequest.created_at.desc())
    if status_filter:
        query = query.where(ApprovalRequest.status == status_filter)
    return [approval_list_row(r) for r in db.scalars(query).all()]


@router.post("", response_model=ApprovalDetailOut, status_code=status.HTTP_201_CREATED)
def submit(data: ApprovalSubmitIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*OFFICERS))):
    """Send the RFQ's selected quotation for approval. The quotation is read from the database, not from the request."""
    return approval_detail(submit_for_approval(db, data.rfq_id, user), user)


@router.get("/{approval_id}", response_model=ApprovalDetailOut)
def read(approval_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*STAFF_ROLES))):
    return approval_detail(load(db, approval_id), user)


@router.post("/{approval_id}/decision", response_model=ApprovalDetailOut)
def decision(approval_id: int, data: DecisionIn, db: Session = Depends(get_db),
             user: User = Depends(require_roles(*APPROVER_ROLES))):
    # lock the row so two approvers clicking at once cannot both decide the same level
    req = db.get(ApprovalRequest, approval_id, with_for_update=True)
    if req is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            "Approval request not found")
    return approval_detail(decide(db, req, user, data.decision == "approve", data.remarks), user)
