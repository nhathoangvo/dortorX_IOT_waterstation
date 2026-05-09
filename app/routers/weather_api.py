from __future__ import annotations
import os
import time
import logging
import requests
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/weather", tags=["weather"])

OPENWEATHER_KEY = os.getenv("OPENWEATHER_API_KEY", "")
CITY            = os.getenv("WEATHER_CITY", "Ho Chi Minh City,VN")
CACHE_TTL       = 600  # 10 phút

_cache: dict = {"data": None, "ts": 0.0}


@router.get("")
def get_weather():
    now = time.time()
    if _cache["data"] and now - _cache["ts"] < CACHE_TTL:
        return _cache["data"]

    if not OPENWEATHER_KEY:
        raise HTTPException(503, "OPENWEATHER_API_KEY chưa được cấu hình")

    try:
        url = (
            f"https://api.openweathermap.org/data/2.5/weather"
            f"?q={CITY}&appid={OPENWEATHER_KEY}&units=metric&lang=vi"
        )
        r = requests.get(url, timeout=6)
        r.raise_for_status()
        d = r.json()
    except Exception as e:
        logger.error("OpenWeatherMap error: %s", e)
        if _cache["data"]:
            return _cache["data"]  # trả cache cũ nếu lỗi
        raise HTTPException(502, "Không lấy được dữ liệu thời tiết")

    result = {
        "city":          d["name"],
        "temperature_c": round(d["main"]["temp"], 1),
        "feels_like_c":  round(d["main"]["feels_like"], 1),
        "humidity_pct":  d["main"]["humidity"],
        "description":   d["weather"][0]["description"],
        "icon":          d["weather"][0]["icon"],
        "wind_speed":    d["wind"]["speed"],
    }
    _cache["data"] = result
    _cache["ts"]   = now
    logger.info("WEATHER fetched city=%s temp=%.1f", result["city"], result["temperature_c"])
    return result
