"""Tests for dashboard schema validation."""

from __future__ import annotations

from autogen.validator.dashboard_schema import (
    VALID_CARD_TYPES,
    check_card_types,
    check_dashboard_schema,
)
from autogen.validator.pipeline import validate_dashboard


# -- check_dashboard_schema --

def test_valid_dashboard_schema() -> None:
    parsed = {
        "views": [
            {"title": "Home", "cards": [{"type": "entities", "entities": ["light.test"]}]}
        ]
    }
    issues = check_dashboard_schema(parsed)
    assert len(issues) == 0


def test_missing_views_key() -> None:
    parsed = {"title": "Bad"}
    issues = check_dashboard_schema(parsed)
    assert len(issues) == 1
    assert issues[0].check_name == "dashboard_schema"
    assert "views" in issues[0].message.lower()


def test_views_not_list() -> None:
    parsed = {"views": "not a list"}
    issues = check_dashboard_schema(parsed)
    assert len(issues) == 1
    assert "list" in issues[0].message.lower()


def test_view_missing_cards_no_error() -> None:
    """Views without cards are valid in Lovelace (cards key is optional)."""
    parsed = {"views": [{"title": "No Cards View"}]}
    issues = check_dashboard_schema(parsed)
    assert len(issues) == 0


def test_empty_views_list() -> None:
    parsed = {"views": []}
    issues = check_dashboard_schema(parsed)
    assert len(issues) == 1
    assert "no views" in issues[0].message.lower()


# -- check_card_types --

def test_valid_card_types() -> None:
    parsed = {
        "views": [
            {
                "title": "Test",
                "cards": [
                    {"type": "entities", "entities": ["light.test"]},
                    {"type": "gauge", "entity": "sensor.temp"},
                ]
            }
        ]
    }
    issues = check_card_types(parsed)
    assert len(issues) == 0


def test_unknown_card_type() -> None:
    parsed = {
        "views": [
            {
                "title": "Test",
                "cards": [{"type": "super-custom-unknown-card"}]
            }
        ]
    }
    issues = check_card_types(parsed)
    assert len(issues) == 1
    assert "super-custom-unknown-card" in issues[0].message


def test_gauge_missing_entity() -> None:
    parsed = {
        "views": [
            {
                "title": "Test",
                "cards": [{"type": "gauge"}]  # missing "entity"
            }
        ]
    }
    issues = check_card_types(parsed)
    assert len(issues) == 1
    assert "entity" in issues[0].message.lower()


def test_stacked_cards_validated() -> None:
    parsed = {
        "views": [
            {
                "title": "Test",
                "cards": [
                    {
                        "type": "horizontal-stack",
                        "cards": [
                            {"type": "fake-card-xyz"}
                        ]
                    }
                ]
            }
        ]
    }
    issues = check_card_types(parsed)
    assert len(issues) == 1
    assert "fake-card-xyz" in issues[0].message


# -- validate_dashboard pipeline --

def test_validate_dashboard_valid() -> None:
    yaml_str = """
views:
  - title: Home
    cards:
      - type: entities
        entities:
          - light.test
"""
    result = validate_dashboard(yaml_str, {"light.test"})
    assert result.valid


def test_validate_dashboard_invalid_yaml() -> None:
    result = validate_dashboard("views:\n  - title: [bad", set())
    assert not result.valid


def test_validate_dashboard_unknown_entity() -> None:
    yaml_str = """
views:
  - title: Home
    cards:
      - type: entities
        entities:
          - light.nonexistent
"""
    result = validate_dashboard(yaml_str, {"light.real"})
    # Should have a warning about unknown entity
    entity_issues = [i for i in result.issues if i.check_name == "entity_refs"]
    assert len(entity_issues) > 0


def test_validate_dashboard_missing_views() -> None:
    yaml_str = "title: bad dashboard\n"
    result = validate_dashboard(yaml_str, set())
    assert not result.valid
