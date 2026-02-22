"""Existing automation config access via HA WebSocket API."""

from __future__ import annotations

import logging
from io import StringIO
from pathlib import Path
from typing import Any

import aiohttp
from ruamel.yaml import YAML

logger = logging.getLogger(__name__)

_yaml = YAML()
_yaml.preserve_quotes = True


async def fetch_automations(
    ws: aiohttp.ClientWebSocketResponse,
    msg_id: int,
    automation_entity_ids: list[str] | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Fetch automation configs via WS automation/config for each entity.

    HA doesn't have a bulk automation config command. We fetch each one
    individually using the ``automation/config`` WS type.

    Returns (configs, next_msg_id).
    """
    if not automation_entity_ids:
        return [], msg_id

    results: list[dict[str, Any]] = []
    current_id = msg_id

    for entity_id in automation_entity_ids:
        await ws.send_json({
            "id": current_id,
            "type": "automation/config",
            "entity_id": entity_id,
        })
        resp = await ws.receive_json()
        if resp.get("success"):
            config = resp["result"].get("config", {})
            config["entity_id"] = entity_id
            results.append(config)
        else:
            logger.debug(
                "Could not fetch config for %s: %s",
                entity_id,
                resp.get("error"),
            )
        current_id += 1

    return results, current_id


def load_automations_from_fixture(fixture_path: Path) -> list[dict[str, Any]]:
    """Load automation configs from a YAML fixture file (dev mode)."""
    if not fixture_path.exists():
        return []
    content = fixture_path.read_text(encoding="utf-8")
    if not content.strip():
        return []
    parsed = _yaml.load(StringIO(content))
    if parsed is None:
        return []
    if isinstance(parsed, list):
        return [dict(a) if hasattr(a, "items") else a for a in parsed]
    return [dict(parsed) if hasattr(parsed, "items") else parsed]
