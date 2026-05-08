from __future__ import annotations
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Device, User
from app.schemas import DeviceCreate, DeviceOut
from app.security import generate_device_api_key
from app.dependencies import get_current_user

router = APIRouter(prefix="/devices", tags=["devices"])


@router.post("", response_model=DeviceOut, status_code=201)
def create_device(body: DeviceCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if db.query(Device).filter(Device.device_id == body.device_id).first():
        raise HTTPException(400, "Device ID đã tồn tại")
    dev = Device(
        device_id=body.device_id,
        name=body.name,
        description=body.description,
        api_key=generate_device_api_key(),
        owner_id=user.id,
    )
    db.add(dev); db.commit(); db.refresh(dev)
    return dev


@router.get("", response_model=List[DeviceOut])
def list_devices(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Device).filter(Device.owner_id == user.id).all()


@router.delete("/{device_id}", status_code=204)
def delete_device(device_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    dev = db.query(Device).filter(Device.device_id == device_id, Device.owner_id == user.id).first()
    if not dev:
        raise HTTPException(404, "Device không tìm thấy")
    db.delete(dev); db.commit()


@router.patch("/{device_id}/regenerate-key", response_model=DeviceOut)
def regenerate_key(device_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    dev = db.query(Device).filter(Device.device_id == device_id, Device.owner_id == user.id).first()
    if not dev:
        raise HTTPException(404, "Device không tìm thấy")
    dev.api_key = generate_device_api_key()
    db.commit(); db.refresh(dev)
    return dev
