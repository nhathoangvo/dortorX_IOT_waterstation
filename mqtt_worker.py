"""
mqtt_worker.py — Doctor.X Production MQTT Worker
- Paho MQTT v2 API
- Username/password auth support
- Exponential backoff reconnect
- Async HTTP queue (non-blocking on_message)
- Graceful shutdown
"""
from __future__ import annotations

import json
import logging
import os
import queue
import signal
import sys
import threading
import time
from typing import Optional

import paho.mqtt.client as mqtt
import requests
from dotenv import load_dotenv

load_dotenv()

# ── CONFIG (override via .env) ──────────────────────────
MQTT_HOST     = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT     = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME")          # None = anonymous
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
MQTT_TOPIC    = os.getenv("MQTT_TOPIC", "doctorx/devices/+/telemetry")
MQTT_TLS      = os.getenv("MQTT_TLS", "false").lower() == "true"

INGEST_URL    = os.getenv("INGEST_URL", "http://localhost:8000/ingest/telemetry")
HTTP_TIMEOUT  = int(os.getenv("HTTP_TIMEOUT", "5"))
HTTP_RETRIES  = int(os.getenv("HTTP_RETRIES", "3"))

LOG_LEVEL     = os.getenv("LOG_LEVEL", "INFO")
# ────────────────────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("mqtt_worker")

# Thread-safe queue — on_message pushes, sender thread pops
_send_queue: queue.Queue = queue.Queue(maxsize=1000)
_running = threading.Event()
_running.set()


# ── HTTP SENDER THREAD ──────────────────────────────────
def _http_sender():
    session = requests.Session()
    while _running.is_set() or not _send_queue.empty():
        try:
            payload = _send_queue.get(timeout=1)
        except queue.Empty:
            continue

        for attempt in range(1, HTTP_RETRIES + 1):
            try:
                r = session.post(INGEST_URL, json=payload, timeout=HTTP_TIMEOUT)
                if r.status_code < 400:
                    logger.info("✓ Forward OK [%s] %s=%.1f", r.status_code, payload.get("metric_type"), payload.get("value", 0))
                else:
                    logger.error("✗ Backend %s: %s", r.status_code, r.text[:200])
                break
            except requests.RequestException as e:
                logger.warning("Attempt %s/%s failed: %s", attempt, HTTP_RETRIES, e)
                if attempt < HTTP_RETRIES:
                    time.sleep(2 ** attempt)

        _send_queue.task_done()


# ── MQTT CALLBACKS ──────────────────────────────────────
def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        logger.info("✓ Connected to MQTT broker %s:%s", MQTT_HOST, MQTT_PORT)
        client.subscribe(MQTT_TOPIC, qos=1)
        logger.info("Subscribed: %s", MQTT_TOPIC)
    else:
        logger.error("✗ MQTT connect failed, reason_code=%s", reason_code)


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties=None):
    if reason_code != 0:
        logger.warning("MQTT disconnected unexpectedly (rc=%s) — will auto-reconnect", reason_code)


def on_message(client, userdata, msg):
    try:
        text = msg.payload.decode("utf-8", errors="ignore").strip()
        data = json.loads(text)

        required = ("device_id", "api_key", "metric_type", "value")
        missing = [k for k in required if k not in data]
        if missing:
            logger.error("Missing keys %s in: %s", missing, text[:200])
            return

        # Validate types
        data["value"] = float(data["value"])

        logger.debug("MQTT → queue  topic=%s device=%s", msg.topic, data.get("device_id"))

        try:
            _send_queue.put_nowait(data)
        except queue.Full:
            logger.warning("Send queue full — dropping message from %s", data.get("device_id"))

    except json.JSONDecodeError:
        logger.error("Invalid JSON on %s: %r", msg.topic, msg.payload[:100])
    except Exception as e:
        logger.exception("on_message error: %s", e)


def on_subscribe(client, userdata, mid, reason_codes, properties=None):
    logger.info("Subscription confirmed mid=%s", mid)


# ── MAIN ────────────────────────────────────────────────
def main():
    # Graceful shutdown on SIGINT / SIGTERM
    def _shutdown(sig, frame):
        logger.info("Shutting down (signal %s)...", sig)
        _running.clear()
        client.loop_stop()
        client.disconnect()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # Start HTTP sender thread
    sender = threading.Thread(target=_http_sender, daemon=True, name="http-sender")
    sender.start()

    # Build MQTT client
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id="doctorx_ingestor",
        clean_session=True,
    )
    client.on_connect    = on_connect
    client.on_disconnect = on_disconnect
    client.on_message    = on_message
    client.on_subscribe  = on_subscribe

    if MQTT_USERNAME:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        logger.info("Auth: username=%s", MQTT_USERNAME)

    if MQTT_TLS:
        import ssl
        client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
        logger.info("TLS enabled")

    # Reconnect settings — exponential backoff 1s→120s
    client.reconnect_delay_set(min_delay=1, max_delay=120)

    logger.info("Connecting to %s:%s (TLS=%s)...", MQTT_HOST, MQTT_PORT, MQTT_TLS)
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_forever(retry_first_connection=True)


if __name__ == "__main__":
    main()
