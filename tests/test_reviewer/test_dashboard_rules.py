"""Tests for deterministic dashboard review rules."""

from __future__ import annotations

from autogen.reviewer.dashboard_rules import (
    check_card_type_recommendations,
    check_inconsistent_cards,
    check_layout_optimization,
    check_missing_area_coverage,
    check_unused_entities,
    run_all_dashboard_rules,
)
from autogen.reviewer.models import FindingCategory


SAMPLE_DASHBOARD = {
    "views": [
        {
            "title": "Living Room",
            "cards": [
                {"type": "entities", "entities": ["light.living", "sensor.temp"]},
                {"type": "gauge", "entity": "sensor.humidity"},
            ],
        },
        {
            "title": "Kitchen",
            "cards": [
                {"type": "entities", "entities": ["light.kitchen", "switch.coffee"]},
            ],
        },
    ]
}


# -- check_unused_entities --

def test_unused_entities_found() -> None:
    known = {"light.living", "sensor.temp", "sensor.humidity", "light.kitchen",
             "switch.coffee", "light.bedroom"}  # bedroom not on dashboard
    findings = check_unused_entities(SAMPLE_DASHBOARD, known)
    assert len(findings) == 1
    assert findings[0].category == FindingCategory.unused_entities
    assert "light.bedroom" in findings[0].description


def test_no_unused_entities() -> None:
    known = {"light.living", "sensor.temp", "sensor.humidity", "light.kitchen",
             "switch.coffee"}
    findings = check_unused_entities(SAMPLE_DASHBOARD, known)
    assert len(findings) == 0


def test_unused_entities_ignores_non_displayable() -> None:
    # automation, script, scene etc. should not be flagged
    known = {"light.living", "sensor.temp", "sensor.humidity", "light.kitchen",
             "switch.coffee", "automation.morning", "script.test"}
    findings = check_unused_entities(SAMPLE_DASHBOARD, known)
    assert len(findings) == 0


# -- check_inconsistent_cards --

def test_inconsistent_cards_detected() -> None:
    findings = check_inconsistent_cards(SAMPLE_DASHBOARD)
    # sensor.temp uses "entities" card, sensor.humidity uses "gauge"
    sensor_findings = [f for f in findings if "sensor" in f.title]
    assert len(sensor_findings) == 1
    assert sensor_findings[0].category == FindingCategory.inconsistent_cards


def test_consistent_cards_no_findings() -> None:
    dashboard = {
        "views": [
            {
                "title": "Test",
                "cards": [
                    {"type": "entities", "entities": ["light.a", "light.b"]},
                ],
            }
        ]
    }
    findings = check_inconsistent_cards(dashboard)
    assert len(findings) == 0


# -- check_missing_area_coverage --

def test_missing_area_coverage() -> None:
    areas = [
        {"name": "Living Room"},
        {"name": "Kitchen"},
        {"name": "Bedroom"},  # no view for this
    ]
    findings = check_missing_area_coverage(SAMPLE_DASHBOARD, areas)
    assert len(findings) == 1
    assert "Bedroom" in findings[0].title


def test_all_areas_covered() -> None:
    areas = [{"name": "Living Room"}, {"name": "Kitchen"}]
    findings = check_missing_area_coverage(SAMPLE_DASHBOARD, areas)
    assert len(findings) == 0


# -- check_card_type_recommendations --

def test_sensor_on_entities_card_suggests_gauge() -> None:
    dashboard = {
        "views": [
            {
                "title": "Test",
                "cards": [
                    {"type": "entities", "entities": ["sensor.temp"]},
                ],
            }
        ]
    }
    findings = check_card_type_recommendations(dashboard)
    gauge_findings = [f for f in findings if "gauge" in f.title]
    assert len(gauge_findings) == 1
    assert gauge_findings[0].category == FindingCategory.card_type_recommendation


def test_sensor_on_gauge_card_no_recommendation() -> None:
    dashboard = {
        "views": [
            {
                "title": "Test",
                "cards": [
                    {"type": "gauge", "entity": "sensor.temp"},
                ],
            }
        ]
    }
    findings = check_card_type_recommendations(dashboard)
    assert len(findings) == 0


def test_climate_entities_card_suggests_thermostat() -> None:
    dashboard = {
        "views": [
            {
                "title": "Test",
                "cards": [
                    {"type": "entities", "entities": ["climate.hvac"]},
                ],
            }
        ]
    }
    findings = check_card_type_recommendations(dashboard)
    thermo_findings = [f for f in findings if "thermostat" in f.title]
    assert len(thermo_findings) == 1


# -- check_layout_optimization --

def test_long_view_flagged() -> None:
    # 9 cards, no stacks
    dashboard = {
        "views": [
            {
                "title": "Long View",
                "cards": [{"type": "entities", "entities": ["light.x"]} for _ in range(9)],
            }
        ]
    }
    findings = check_layout_optimization(dashboard)
    assert len(findings) == 1
    assert findings[0].category == FindingCategory.layout_optimization
    assert "Long View" in findings[0].title


def test_short_view_not_flagged() -> None:
    dashboard = {
        "views": [
            {
                "title": "Short",
                "cards": [{"type": "entities", "entities": ["light.x"]} for _ in range(4)],
            }
        ]
    }
    findings = check_layout_optimization(dashboard)
    assert len(findings) == 0


def test_long_view_with_stacks_not_flagged() -> None:
    dashboard = {
        "views": [
            {
                "title": "Organized",
                "cards": [
                    {"type": "horizontal-stack", "cards": [
                        {"type": "entities", "entities": ["light.a"]},
                        {"type": "entities", "entities": ["light.b"]},
                    ]},
                    *[{"type": "entities", "entities": ["light.x"]} for _ in range(8)],
                ],
            }
        ]
    }
    findings = check_layout_optimization(dashboard)
    assert len(findings) == 0


# -- Integration: run_all_dashboard_rules --

def test_run_all_dashboard_rules() -> None:
    known = {"light.living", "sensor.temp", "sensor.humidity", "light.kitchen",
             "switch.coffee", "light.bedroom"}
    areas = [{"name": "Living Room"}, {"name": "Kitchen"}, {"name": "Bedroom"}]

    findings = run_all_dashboard_rules(SAMPLE_DASHBOARD, known, areas)

    categories = {f.category for f in findings}
    # Should find: unused_entities (bedroom light), inconsistent_cards (sensors),
    # missing_area_coverage (Bedroom), card_type_recommendations (sensors on entities card)
    assert FindingCategory.unused_entities in categories
    assert FindingCategory.inconsistent_cards in categories
    assert FindingCategory.missing_area_coverage in categories


def test_run_all_dashboard_rules_clean() -> None:
    clean_dashboard = {
        "views": [
            {
                "title": "Home",
                "cards": [
                    {"type": "gauge", "entity": "sensor.temp"},
                ],
            }
        ]
    }
    findings = run_all_dashboard_rules(clean_dashboard)
    assert len(findings) == 0
