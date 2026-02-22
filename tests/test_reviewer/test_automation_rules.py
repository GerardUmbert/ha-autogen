"""Tests for deterministic automation review rules."""

from __future__ import annotations

from autogen.reviewer.automation_rules import (
    check_deprecated_patterns,
    check_missing_guards,
    check_security_concerns,
    check_trigger_efficiency,
    run_all_rules,
)
from autogen.reviewer.models import FindingCategory, FindingSeverity


def _make_automation(
    triggers=None,
    conditions=None,
    actions=None,
    auto_id="test_auto",
    alias="Test Automation",
) -> dict:
    auto = {"id": auto_id, "alias": alias}
    if triggers is not None:
        auto["trigger"] = triggers
    if conditions is not None:
        auto["condition"] = conditions
    if actions is not None:
        auto["action"] = actions
    return auto


# -- Trigger efficiency --

def test_time_pattern_seconds_flagged() -> None:
    auto = _make_automation(
        triggers=[{"platform": "time_pattern", "seconds": "/5"}],
    )
    findings = check_trigger_efficiency(auto)
    assert len(findings) == 1
    assert findings[0].category == FindingCategory.trigger_efficiency


def test_state_trigger_not_flagged() -> None:
    auto = _make_automation(
        triggers=[{"platform": "state", "entity_id": "light.living_room"}],
    )
    findings = check_trigger_efficiency(auto)
    assert len(findings) == 0


# -- Missing guards --

def test_no_conditions_flagged() -> None:
    auto = _make_automation(
        triggers=[{"platform": "state", "entity_id": "sensor.motion"}],
        actions=[{"service": "light.turn_on"}],
    )
    findings = check_missing_guards(auto)
    assert len(findings) == 1
    assert findings[0].severity == FindingSeverity.suggestion


def test_with_conditions_not_flagged() -> None:
    auto = _make_automation(
        triggers=[{"platform": "state", "entity_id": "sensor.motion"}],
        conditions=[{"condition": "time", "after": "22:00:00"}],
        actions=[{"service": "light.turn_on"}],
    )
    findings = check_missing_guards(auto)
    assert len(findings) == 0


# -- Security concerns --

def test_lock_without_conditions_critical() -> None:
    auto = _make_automation(
        triggers=[{"platform": "state"}],
        actions=[{"service": "lock.lock", "target": {"entity_id": "lock.front_door"}}],
    )
    findings = check_security_concerns(auto)
    assert len(findings) == 1
    assert findings[0].severity == FindingSeverity.critical
    assert "lock" in findings[0].title.lower()


def test_lock_with_conditions_warning() -> None:
    auto = _make_automation(
        triggers=[{"platform": "state"}],
        conditions=[{"condition": "time", "after": "22:00:00"}],
        actions=[{"service": "lock.unlock", "target": {"entity_id": "lock.front_door"}}],
    )
    findings = check_security_concerns(auto)
    assert len(findings) == 1
    assert findings[0].severity == FindingSeverity.warning


def test_nonsensitive_domain_no_findings() -> None:
    auto = _make_automation(
        triggers=[{"platform": "state"}],
        actions=[{"service": "light.turn_on", "target": {"entity_id": "light.kitchen"}}],
    )
    findings = check_security_concerns(auto)
    assert len(findings) == 0


# -- Deprecated patterns --

def test_homeassistant_turn_on_flagged() -> None:
    auto = _make_automation(
        actions=[{
            "service": "homeassistant.turn_on",
            "target": {"entity_id": "light.bedroom"},
        }],
    )
    findings = check_deprecated_patterns(auto)
    assert len(findings) == 1
    assert findings[0].category == FindingCategory.deprecated_patterns
    assert "light.turn_on" in findings[0].description


def test_domain_specific_not_flagged() -> None:
    auto = _make_automation(
        actions=[{"service": "light.turn_on", "target": {"entity_id": "light.bedroom"}}],
    )
    findings = check_deprecated_patterns(auto)
    assert len(findings) == 0


# -- Integration: run_all_rules --

def test_run_all_rules_multiple_findings() -> None:
    auto = _make_automation(
        triggers=[{"platform": "time_pattern", "seconds": "/10"}],
        actions=[{
            "service": "homeassistant.turn_on",
            "data": {"entity_id": "lock.front_door"},
        }],
    )
    findings = run_all_rules(auto)
    # Should have: trigger_efficiency, missing_guards, security (lock without conds), deprecated_patterns
    categories = {f.category for f in findings}
    assert FindingCategory.trigger_efficiency in categories
    assert FindingCategory.missing_guards in categories
    assert FindingCategory.security in categories
    assert FindingCategory.deprecated_patterns in categories


def test_clean_automation_no_findings() -> None:
    auto = _make_automation(
        triggers=[{"platform": "state", "entity_id": "binary_sensor.motion"}],
        conditions=[{"condition": "sun", "after": "sunset"}],
        actions=[{"service": "light.turn_on", "target": {"entity_id": "light.porch"}}],
    )
    findings = run_all_rules(auto)
    assert len(findings) == 0
