from __future__ import annotations
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas import UserOut, WaterHistoryDay, RoleUpdate
from app.dependencies import require_admin
from app.services import water as svc

logger = logging.getLogger("security")
router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=List[UserOut])
def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return db.query(User).order_by(User.created_at.desc()).all()


@router.get("/users/{user_id}/water/history", response_model=List[WaterHistoryDay])
def user_water_history(
    user_id: int,
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    return svc.get_history(db, user, days)


@router.patch("/users/{user_id}/role")
def update_user_role(
    user_id: int,
    body: RoleUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    if user.id == admin.id:
        raise HTTPException(400, "Cannot change your own role")
    old_role = user.role
    user.role = body.role
    db.commit()
    logger.info("ROLE_CHANGE admin_id=%s target=%s %s→%s", admin.id, user_id, old_role, body.role)
    return {"ok": True, "role": user.role}
