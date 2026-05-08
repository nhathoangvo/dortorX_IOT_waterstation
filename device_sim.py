"""
device_sim.py — Doctor.X Device Simulator
Simulates realistic water intake patterns for multiple devices.
Supports MQTT publish OR direct HTTP POST.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
MQTT_HOST   = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT   = int(os.getenv("MQTT_PORT", "1883"))

# Realistic drinking schedule (hour -> probability weight of drinking)
DRINK_SCHEDULE = {
    6: 0.8, 7: 1.5, 8: 1.2, 9: 0.8, 10: 1.0,
    11: 1.0, 12: 1.8, 13: 1.0, 14: 0.8, 15: 1.2,
    16: 1.0, 17: 0.8, 18: 1.5, 19: 0.8, 20: 0.5, 21: 0.3,
}
SIPS = [100, 150, 150, 200, 200, 200, 250, 250, 300]  # ml options


def send_http(device_id: str, api_key: str, volume_ml: float) -> bool:
    payload = {
        "device_id": device_id,
        "api_key": api_key,
        "metric_type": "water_intake_ml",
        "value": volume_ml,
        "payload": {"volume_ml": volume_ml, "source": "simulator"},
    }
    try:
        r = requests.post(f"{BACKEND_URL}/ingest/telemetry", json=payload, timeout=5)
        ok = r.status_code < 400
        status = "✓" if ok else "✗"
        print(f"[{datetime.now():%H:%M:%S}] {status} HTTP {device_id} {volume_ml}ml → {r.status_code}")
        return ok
    except Exception as e:
        print(f"[{datetime.now():%H:%M:%S}] ✗ HTTP error: {e}")
        return False


def send_mqtt(client, device_id: str, api_key: str, volume_ml: float):
    import paho.mqtt.client as mqtt_mod
    topic = f"doctorx/devices/{device_id}/telemetry"
    payload = json.dumps({
        "device_id": device_id,
        "api_key": api_key,
        "metric_type": "water_intake_ml",
        "value": volume_ml,
        "payload": {"volume_ml": volume_ml, "source": "simulator"},
    })
    result = client.publish(topic, payload, qos=1)
    status = "✓" if result.rc == 0 else "✗"
    print(f"[{datetime.now():%H:%M:%S}] {status} MQTT {topic} {volume_ml}ml")


def realistic_interval() -> float:
    """Return seconds until next simulated drink based on hour of day."""
    hour = datetime.now().hour
    weight = DRINK_SCHEDULE.get(hour, 0.2)
    base = random.uniform(30, 120)  # 30s–2min in sim (represents ~30min real)
    return base / weight


def run_http_mode(devices: list[dict], duration_s: int):
    print(f"▶ HTTP mode — {len(devices)} device(s) — duration {duration_s}s")
    end = time.time() + duration_s
    while time.time() < end:
        dev = random.choice(devices)
        vol = random.choice(SIPS)
        send_http(dev["device_id"], dev["api_key"], vol)
        time.sleep(realistic_interval())
    print("✓ Simulation complete")


def run_mqtt_mode(devices: list[dict], duration_s: int):
    import paho.mqtt.client as mqtt_mod

    username = os.getenv("MQTT_USERNAME")
    password = os.getenv("MQTT_PASSWORD")

    client = mqtt_mod.Client(mqtt_mod.CallbackAPIVersion.VERSION2, client_id="doctorx_sim")
    if username:
        client.username_pw_set(username, password)

    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_start()

    print(f"▶ MQTT mode — {len(devices)} device(s) — duration {duration_s}s")
    end = time.time() + duration_s
    while time.time() < end:
        dev = random.choice(devices)
        vol = random.choice(SIPS)
        send_mqtt(client, dev["device_id"], dev["api_key"], vol)
        time.sleep(realistic_interval())

    client.loop_stop()
    client.disconnect()
    print("✓ Simulation complete")


def main():
    parser = argparse.ArgumentParser(description="Doctor.X Device Simulator")
    parser.add_argument("--device", nargs="+", metavar="ID:KEY",
                        help="device_id:api_key pairs (space separated). E.g. dev01:abc123 dev02:xyz456")
    parser.add_argument("--mode", choices=["http", "mqtt"], default="http")
    parser.add_argument("--duration", type=int, default=300, help="Duration in seconds (default 300)")
    args = parser.parse_args()

    if not args.device:
        # Quick test with env vars
        device_id = os.getenv("SIM_DEVICE_ID", "water_station")
        api_key   = os.getenv("SIM_API_KEY", "")
        if not api_key:
            print("ERROR: Provide --device ID:KEY or set SIM_DEVICE_ID / SIM_API_KEY env vars")
            sys.exit(1)
        devices = [{"device_id": device_id, "api_key": api_key}]
    else:
        devices = []
        for item in args.device:
            parts = item.split(":", 1)
            if len(parts) != 2:
                print(f"ERROR: Invalid format '{item}'. Use device_id:api_key")
                sys.exit(1)
            devices.append({"device_id": parts[0], "api_key": parts[1]})

    if args.mode == "mqtt":
        run_mqtt_mode(devices, args.duration)
    else:
        run_http_mode(devices, args.duration)


if __name__ == "__main__":
    main()
