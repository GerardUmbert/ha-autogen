"""Tests for entity reference validation."""

from autogen.validator.entity_refs import check_entity_refs


KNOWN_ENTITIES = {
    "light.living_room",
    "light.kitchen",
    "switch.bedroom_fan",
    "sensor.temperature",
    "binary_sensor.motion",
    "climate.thermostat",
    "media_player.living_room_tv",
}


def test_all_known_entities():
    parsed = {
        "trigger": {"platform": "state", "entity_id": "light.living_room"},
        "action": {"service": "light.turn_on", "target": {"entity_id": "light.kitchen"}},
    }
    issues = check_entity_refs(parsed, KNOWN_ENTITIES)
    assert len(issues) == 0


def test_unknown_entity():
    parsed = {
        "action": {"service": "light.turn_on", "target": {"entity_id": "light.garage"}},
    }
    issues = check_entity_refs(parsed, KNOWN_ENTITIES)
    assert len(issues) == 1
    assert issues[0].check_name == "entity_refs"
    assert issues[0].severity.value == "warning"
    assert "light.garage" in issues[0].message


def test_fuzzy_suggestion():
    parsed = {
        "action": {"target": {"entity_id": "light.livng_room"}},  # typo
    }
    issues = check_entity_refs(parsed, KNOWN_ENTITIES)
    assert len(issues) == 1
    assert issues[0].suggestion is not None
    assert "light.living_room" in issues[0].suggestion


def test_entity_id_list():
    """Entity IDs specified as a list should all be checked."""
    parsed = {
        "action": {
            "target": {
                "entity_id": [
                    "light.living_room",
                    "light.kitchen",
                    "light.nonexistent",
                ]
            }
        },
    }
    issues = check_entity_refs(parsed, KNOWN_ENTITIES)
    assert len(issues) == 1
    assert "light.nonexistent" in issues[0].message


def test_nested_entity_refs():
    """Entity refs nested deep in the YAML structure."""
    parsed = {
        "action": [
            {
                "choose": [
                    {
                        "conditions": [
                            {"entity_id": "binary_sensor.motion"},
                        ],
                        "sequence": [
                            {"service": "light.turn_on", "target": {"entity_id": "light.unknown_room"}},
                        ],
                    }
                ]
            }
        ],
    }
    issues = check_entity_refs(parsed, KNOWN_ENTITIES)
    assert len(issues) == 1
    assert "light.unknown_room" in issues[0].message


def test_no_entity_refs():
    """YAML with no entity_id fields should produce no issues."""
    parsed = {
        "alias": "Test",
        "trigger": {"platform": "time", "at": "07:00:00"},
        "action": {"service": "script.morning_routine"},
    }
    issues = check_entity_refs(parsed, KNOWN_ENTITIES)
    assert len(issues) == 0


def test_empty_known_entities():
    """When known set is empty, all entities are flagged as unknown."""
    parsed = {
        "trigger": {"entity_id": "light.living_room"},
    }
    issues = check_entity_refs(parsed, set())
    assert len(issues) == 1
