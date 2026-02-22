"""Export Home Assistant entity and area registries to fixture files.

Usage (PowerShell):
    python scripts/export_ha_context.py --url http://homeassistant.local:8123 --token YOUR_TOKEN
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import aiohttp

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


async def export_registries(ha_url: str, token: str) -> None:
    ws_url = ha_url.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = ws_url.rstrip("/") + "/api/websocket"

    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(ws_url) as ws:
            # Auth handshake
            auth_msg = await ws.receive_json()
            if auth_msg.get("type") != "auth_required":
                raise RuntimeError(f"Unexpected message: {auth_msg}")

            await ws.send_json({"type": "auth", "access_token": token})
            auth_resp = await ws.receive_json()
            if auth_resp.get("type") != "auth_ok":
                raise RuntimeError(f"Auth failed: {auth_resp}")

            print(f"Connected to HA {auth_resp.get('ha_version', 'unknown')}")

            msg_id = 1

            # Entity registry
            await ws.send_json({"id": msg_id, "type": "config/entity_registry/list"})
            resp = await ws.receive_json()
            if not resp.get("success"):
                raise RuntimeError(f"Entity registry failed: {resp}")
            entities = resp["result"]
            msg_id += 1

            # Area registry
            await ws.send_json({"id": msg_id, "type": "config/area_registry/list"})
            resp = await ws.receive_json()
            if not resp.get("success"):
                raise RuntimeError(f"Area registry failed: {resp}")
            areas = resp["result"]
            msg_id += 1

            # Device registry
            await ws.send_json({"id": msg_id, "type": "config/device_registry/list"})
            resp = await ws.receive_json()
            if not resp.get("success"):
                raise RuntimeError(f"Device registry failed: {resp}")
            devices = resp["result"]

    # Write fixture files
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    entity_path = FIXTURES_DIR / "entity_registry.json"
    entity_path.write_text(json.dumps(entities, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Exported {len(entities)} entities to {entity_path}")

    area_path = FIXTURES_DIR / "area_registry.json"
    area_path.write_text(json.dumps(areas, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Exported {len(areas)} areas to {area_path}")

    device_path = FIXTURES_DIR / "device_registry.json"
    device_path.write_text(json.dumps(devices, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Exported {len(devices)} devices to {device_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export HA registries to fixture files")
    parser.add_argument("--url", required=True, help="HA URL (e.g. http://homeassistant.local:8123)")
    parser.add_argument("--token", required=True, help="Long-lived access token")
    args = parser.parse_args()

    asyncio.run(export_registries(args.url, args.token))


if __name__ == "__main__":
    main()
