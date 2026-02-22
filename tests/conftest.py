"""Shared test fixtures and configuration."""

import os
from pathlib import Path

import pytest

os.environ["AUTOGEN_DEV_MODE"] = "true"

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def entity_fixture_path(fixtures_dir: Path) -> Path:
    return fixtures_dir / "entity_registry.json"


@pytest.fixture
def area_fixture_path(fixtures_dir: Path) -> Path:
    return fixtures_dir / "area_registry.json"
