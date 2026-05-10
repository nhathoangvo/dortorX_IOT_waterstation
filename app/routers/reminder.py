from __future__ import annotations
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.db import SessionLocal
from app.models import User
from app.services import water as svc
from app.security import send_reminder_email

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone="Asia/Ho_Chi_Minh")

# (hour, minute, max_percent_to_trigger, slot_name)
_SCHEDULE = [
    (8,  0,   1,  "morning"),    # 8:00 SA  — chưa uống gì
    (12, 0,  30,  "lunch"),      # 12:00 Trưa — < 30%
    (15, 0,  60,  "afternoon"),  # 15:00 Chiều — < 60%
    (20, 0,  90,  "evening"),    # 20:00 Tối  — < 90%
]


async def _send_reminders(threshold_pct: float, slot: str) -> None:
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.is_active == True).all()
        sent = 0
        for user in users:
            try:
                summary = svc.get_today_summary(db, user)
                if summary.percent < threshold_pct:
                    send_reminder_email(
                        email=user.email,
                        name=user.full_name or user.email.split("@")[0],
                        total_ml=summary.total_ml,
                        target_ml=summary.target_ml,
                        percent=summary.percent,
                        slot=slot,
                    )
                    sent += 1
            except Exception as e:
                logger.error("REMINDER_FAIL user_id=%s err=%s", user.id, e)
        logger.info("REMINDER slot=%s sent=%d/%d", slot, sent, len(users))
    finally:
        db.close()


def start_scheduler() -> None:
    for hour, minute, threshold, slot in _SCHEDULE:
        scheduler.add_job(
            _send_reminders,
            CronTrigger(hour=hour, minute=minute, timezone="Asia/Ho_Chi_Minh"),
            args=[threshold, slot],
            id=f"remind_{slot}",
            replace_existing=True,
        )
    scheduler.start()
    logger.info("REMINDER_SCHEDULER started — 4 jobs/day (VN time)")


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
