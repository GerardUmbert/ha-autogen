"""Tests for the deploy engine, backup, and rollback."""

from __future__ import annotations

from pathlib import Path

import pytest

from autogen.deployer.backup import create_backup
from autogen.deployer.engine import DeployEngine, _ensure_automation_id, _slugify


# -- Unit tests for helpers --

def test_slugify_basic() -> None:
    assert _slugify("Turn On Lights") == "turn_on_lights"


def test_slugify_special_chars() -> None:
    assert _slugify("Motion @ Night!") == "motion_night"


def test_slugify_empty() -> None:
    assert _slugify("") == "autogen_automation"


def test_slugify_truncates_long() -> None:
    result = _slugify("a" * 100)
    assert len(result) <= 64


def test_ensure_automation_id_adds_id() -> None:
    auto = {"alias": "Test Auto"}
    aid = _ensure_automation_id(auto)
    assert "id" in auto
    assert aid.startswith("test_auto_")
    assert len(aid) > len("test_auto_")


def test_ensure_automation_id_keeps_existing() -> None:
    auto = {"id": "my_custom_id", "alias": "Test"}
    aid = _ensure_automation_id(auto)
    assert aid == "my_custom_id"


# -- Deploy engine integration tests --

@pytest.mark.asyncio
async def test_deploy_new_automation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AUTOGEN_DEV_MODE", "true")

    engine = DeployEngine()
    engine._config_dir = tmp_path
    engine._dev_mode = True

    yaml_str = 'alias: "Test Light"\ntrigger:\n  - platform: state\naction:\n  - service: light.turn_on\n'
    result = await engine.deploy(yaml_str, backup_enabled=False)

    assert "automation_id" in result
    assert result["replaced"] is False

    # File should exist
    autos = engine.read_current_automations()
    assert len(autos) == 1
    assert autos[0]["alias"] == "Test Light"


@pytest.mark.asyncio
async def test_deploy_replaces_existing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AUTOGEN_DEV_MODE", "true")

    engine = DeployEngine()
    engine._config_dir = tmp_path
    engine._dev_mode = True

    # Deploy first version
    yaml_v1 = 'id: "test_id"\nalias: "Version 1"\ntrigger:\n  - platform: state\naction:\n  - service: light.turn_on\n'
    await engine.deploy(yaml_v1, backup_enabled=False)

    # Deploy second version with same id
    yaml_v2 = 'id: "test_id"\nalias: "Version 2"\ntrigger:\n  - platform: time\naction:\n  - service: light.turn_off\n'
    result = await engine.deploy(yaml_v2, backup_enabled=False)

    assert result["replaced"] is True
    autos = engine.read_current_automations()
    assert len(autos) == 1
    assert autos[0]["alias"] == "Version 2"


@pytest.mark.asyncio
async def test_deploy_empty_yaml_raises(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AUTOGEN_DEV_MODE", "true")

    engine = DeployEngine()
    engine._config_dir = tmp_path
    engine._dev_mode = True

    with pytest.raises(ValueError, match="empty"):
        await engine.deploy("", backup_enabled=False)


@pytest.mark.asyncio
async def test_read_empty_automations(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AUTOGEN_DEV_MODE", "true")

    engine = DeployEngine()
    engine._config_dir = tmp_path
    engine._dev_mode = True

    assert engine.read_current_automations() == []


# -- Backup tests --

def test_create_backup(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AUTOGEN_DEV_MODE", "true")

    source = tmp_path / "automations.yaml"
    source.write_text("- alias: test\n")

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    monkeypatch.setattr(
        "autogen.deployer.backup._get_backup_dir", lambda: backup_dir
    )

    backup_path = create_backup(source)
    assert backup_path.exists()
    assert backup_path.read_text() == "- alias: test\n"


def test_create_backup_nonexistent_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        create_backup(tmp_path / "nonexistent.yaml")
