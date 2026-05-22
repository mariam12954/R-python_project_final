from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.models.audit_log import AuditLog
from app.schemas.audit_log import AuditLogOut
from app.dependencies import get_db, require_admin

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


@router.get("/", response_model=List[AuditLogOut])
def get_logs(
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    return db.query(AuditLog).order_by(AuditLog.timestamp.desc()).all()
