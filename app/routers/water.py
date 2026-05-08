from __future__ import annotations
import csv
import io
from typing import List
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas import WaterSummaryOut, WaterHistoryOut, DashboardOut, UserOut, UserUpdate
from app.services import water as svc
from app.dependencies import get_current_user

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/profile", response_model=UserOut)
def get_profile(user: User = Depends(get_current_user)):
    return user


@router.patch("/profile", response_model=UserOut)
def update_profile(body: UserUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(user, field, val)
    db.commit(); db.refresh(user)
    return user


@router.get("/water/summary-today", response_model=WaterSummaryOut)
def today_summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return svc.get_today_summary(db, user)


@router.get("/water/history", response_model=WaterHistoryOut)
def water_history(days: int = Query(7, ge=1, le=30), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return WaterHistoryOut(days=svc.get_history(db, user, days))


@router.get("/water/export")
def export_water_csv(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    history = svc.get_history(db, user, days)
    target = svc.calc_daily_target(user)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["date", "total_ml", "target_ml", "percent", "achieved"])
    for day in history:
        writer.writerow([day.date, round(day.total_ml), round(target), round(day.percent, 1), day.achieved])
    filename = f"water_history_{days}d.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/water/dashboard", response_model=DashboardOut)
def dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.schemas import DeviceOut
    from app.models import Device
    devices = db.query(Device).filter(Device.owner_id == user.id).all()
    return DashboardOut(
        today=svc.get_today_summary(db, user),
        last_7_days=svc.get_history(db, user, 7),
        hourly_today=svc.get_hourly_today(db, user),
        devices=[DeviceOut.model_validate(d) for d in devices],
    )
