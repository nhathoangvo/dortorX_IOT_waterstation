from __future__ import annotations
import hmac
import logging
from typing import List
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import require_admin
from app.models import Device, FirmwareVersion, User
from app.schemas import FirmwareCreate, FirmwareOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/firmware", tags=["firmware"])


def _get_device(db: Session, device_id: str, api_key: str) -> Device:
    device = db.query(Device).filter(Device.device_id == device_id, Device.is_active == True).first()
    if not device or not hmac.compare_digest(device.api_key, api_key):
        raise HTTPException(401, "Invalid device credentials")
    return device


@router.get("/check")
def check_firmware(
    x_device_id: str = Header(...),
    x_api_key: str = Header(...),
    x_current_version: str = Header(...),
    db: Session = Depends(get_db),
):
    _get_device(db, x_device_id, x_api_key)
    latest = db.query(FirmwareVersion).filter(FirmwareVersion.is_latest == True).first()
    if not latest:
        return {"update_available": False}
    update_available = latest.version != x_current_version
    return {
        "update_available": update_available,
        "version": latest.version,
        "download_url": latest.download_url if update_available else None,
        "release_notes": latest.release_notes if update_available else None,
    }


@router.post("/release", response_model=FirmwareOut)
def create_release(
    body: FirmwareCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if db.query(FirmwareVersion).filter(FirmwareVersion.version == body.version).first():
        raise HTTPException(400, f"Version {body.version} already exists")
    db.query(FirmwareVersion).filter(FirmwareVersion.is_latest == True).update({"is_latest": False})
    fw = FirmwareVersion(
        version=body.version,
        download_url=body.download_url,
        release_notes=body.release_notes,
        is_latest=True,
    )
    db.add(fw)
    db.commit()
    db.refresh(fw)
    logger.info("FIRMWARE_RELEASE version=%s admin_id=%s", fw.version, admin.id)
    return fw


@router.get("/releases", response_model=List[FirmwareOut])
def list_releases(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return db.query(FirmwareVersion).order_by(FirmwareVersion.created_at.desc()).all()
