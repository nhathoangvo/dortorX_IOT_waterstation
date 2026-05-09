from __future__ import annotations
import hmac
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.limiter import limiter
from app.models import Device, Telemetry
from app.schemas import TelemetryIn
from app.ws_manager import manager
from app.services import water as water_svc

router = APIRouter(prefix="/ingest", tags=["ingest"])


async def _push_update(device: Device, db: Session):
    try:
        from app.models import User, Telemetry
        from app.services import water as water_svc2
        user = db.query(User).filter(User.id == device.owner_id).first()
        if not user:
            return
        summary = water_svc.get_today_summary(db, user)

        device_ids = water_svc2.get_device_ids(db, user)
        def _latest_val(metric: str):
            row = (db.query(Telemetry)
                   .filter(Telemetry.device_id.in_(device_ids), Telemetry.metric_type == metric)
                   .order_by(Telemetry.ts.desc()).first())
            return row.value if row else None

        await manager.broadcast_to_user(device.owner_id, {
            "type": "telemetry_update",
            "data": summary.model_dump(),
            "env": {
                "temperature_c": _latest_val("temperature_c"),
                "humidity_pct":  _latest_val("humidity_pct"),
            },
        })
    except Exception as e:
        print("WS push error:", e)


@router.post("/telemetry", status_code=200)
@limiter.limit("100/minute")
async def ingest_telemetry(
    request: Request,
    data: TelemetryIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    dev = db.query(Device).filter(Device.device_id == data.device_id).first()
    if not dev:
        raise HTTPException(400, "Unknown device_id")
    if not hmac.compare_digest(dev.api_key, data.api_key):
        raise HTTPException(403, "Invalid API key")
    if not dev.is_active:
        raise HTTPException(403, "Device is disabled")

    row = Telemetry(
        device_id=data.device_id,
        metric_type=data.metric_type,
        value=data.value,
        payload=data.payload,
    )
    db.add(row)
    dev.last_seen = datetime.utcnow()
    db.commit()

    background_tasks.add_task(_push_update, dev, db)
    return {"status": "ok", "id": row.id}
