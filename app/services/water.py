from __future__ import annotations
from datetime import datetime, timedelta, date
from typing import List, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import User, Device, Telemetry
from app.schemas import WaterSummaryOut, WaterHistoryDay, HourlyPoint


def vn_now() -> datetime:
    return datetime.utcnow() + timedelta(hours=7)


def vn_today() -> date:
    return vn_now().date()


def calc_daily_target(user: User) -> float:
    if not user.weight_kg:
        return 2000.0
    return user.weight_kg * (35 if user.gender == "male" else 31)


def classify_plant_state(total_ml: float, target_ml: float) -> str:
    pct = total_ml / target_ml if target_ml else 0
    if pct < 0.25:
        return "dry"
    elif pct < 0.60:
        return "growing"
    elif pct < 1.0:
        return "healthy"
    return "bloom"


def get_time_slot(now: Optional[datetime] = None) -> str:
    h = (now or vn_now()).hour
    if 5 <= h < 11:
        return "morning"
    elif 11 <= h < 14:
        return "lunch"
    elif 14 <= h < 18:
        return "afternoon"
    return "night"


def get_plant_image(state: str, slot: str) -> str:
    return f"plant_{state}_{slot}.png"


def get_device_ids(db: Session, user: User) -> List[str]:
    return [d.device_id for d in db.query(Device).filter(Device.owner_id == user.id, Device.is_active == True).all()]


def day_range_utc(d: date):
    """Return (start, end) UTC datetimes for a VN calendar day."""
    start = datetime(d.year, d.month, d.day) - timedelta(hours=7)
    return start, start + timedelta(days=1)


def total_ml_for_day(db: Session, device_ids: List[str], d: date) -> float:
    if not device_ids:
        return 0.0
    start, end = day_range_utc(d)
    result = (
        db.query(func.sum(Telemetry.value))
        .filter(
            Telemetry.device_id.in_(device_ids),
            Telemetry.metric_type == "water_intake_ml",
            Telemetry.ts >= start,
            Telemetry.ts < end,
        )
        .scalar()
    )
    return float(result or 0.0)


def calc_streak(db: Session, device_ids: List[str], target_ml: float) -> int:
    """Count consecutive days (ending yesterday) where user hit their target."""
    streak = 0
    today = vn_today()
    for i in range(1, 31):
        d = today - timedelta(days=i)
        if total_ml_for_day(db, device_ids, d) >= target_ml:
            streak += 1
        else:
            break
    return streak


def get_today_summary(db: Session, user: User) -> WaterSummaryOut:
    device_ids = get_device_ids(db, user)
    today = vn_today()
    target = calc_daily_target(user)
    total = total_ml_for_day(db, device_ids, today)
    percent = min(total / target * 100.0, 100.0) if target else 0.0
    state = classify_plant_state(total, target)
    slot = get_time_slot()
    streak = calc_streak(db, device_ids, target)

    return WaterSummaryOut(
        date=today.isoformat(),
        total_ml=total,
        target_ml=target,
        percent=percent,
        plant_state=state,
        time_slot=slot,
        image=get_plant_image(state, slot),
        streak_days=streak,
        glasses=int(total // 250),
    )


def get_history(db: Session, user: User, days: int = 7) -> List[WaterHistoryDay]:
    device_ids = get_device_ids(db, user)
    today = vn_today()
    target = calc_daily_target(user)
    result = []
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        total = total_ml_for_day(db, device_ids, d)
        pct = min(total / target * 100.0, 100.0) if target else 0.0
        result.append(WaterHistoryDay(
            date=d.isoformat(),
            total_ml=total,
            percent=pct,
            achieved=total >= target,
        ))
    return result


def get_hourly_today(db: Session, user: User) -> List[HourlyPoint]:
    device_ids = get_device_ids(db, user)
    if not device_ids:
        return []
    today = vn_today()
    start, end = day_range_utc(today)
    rows = (
        db.query(Telemetry)
        .filter(
            Telemetry.device_id.in_(device_ids),
            Telemetry.metric_type == "water_intake_ml",
            Telemetry.ts >= start,
            Telemetry.ts < end,
        )
        .all()
    )
    hourly: dict[int, float] = {}
    for r in rows:
        vn_hour = ((r.ts + timedelta(hours=7)).hour)
        hourly[vn_hour] = hourly.get(vn_hour, 0.0) + r.value
    return [HourlyPoint(hour=h, total_ml=hourly.get(h, 0.0)) for h in range(24)]
