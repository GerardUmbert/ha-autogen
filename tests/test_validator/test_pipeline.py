"""Tests for the full validation pipeline."""

from autogen.validator import validate, ValidationSeverity


KNOWN_ENTITIES = {
    "light.living_room",
    "light.kitchen",
    "switch.bedroom_fan",
    "sensor.temperature",
    "binary_sensor.motion",
}


def test_valid_yaml_known_entities():
    yaml_str = """
alias: Motion Light
trigger:
  - platform: state
    entity_id: binary_sensor.motion
    to: "on"
action:
  - service: light.turn_on
    target:
      entity_id: light.living_room
"""
    result = validate(yaml_str, KNOWN_ENTITIES)
    assert result.valid is True
    assert len(result.issues) == 0
    assert result.yaml_parsed is not None


def test_invalid_yaml_stops_early():
    yaml_str = "invalid: [unclosed"
    result = validate(yaml_str, KNOWN_ENTITIES)
    assert result.valid is False
    assert len(result.issues) == 1
    assert result.issues[0].check_name == "yaml_syntax"


def test_valid_yaml_unknown_entity():
    yaml_str = """
alias: Test
trigger:
  - platform: state
    entity_id: light.nonexistent
action:
  - service: light.turn_on
    target:
      entity_id: light.kitchen
"""
    result = validate(yaml_str, KNOWN_ENTITIES)
    assert result.valid is True  # warnings don't make it invalid
    entity_issues = [i for i in result.issues if i.check_name == "entity_refs"]
    assert len(entity_issues) == 1
    assert entity_issues[0].severity == ValidationSeverity.warning


def test_valid_yaml_unknown_service_domain():
    yaml_str = """
alias: Test
action:
  - service: foobar.do_thing
"""
    result = validate(yaml_str, KNOWN_ENTITIES)
    assert result.valid is True
    service_issues = [i for i in result.issues if i.check_name == "service_calls"]
    assert len(service_issues) == 1


def test_multiple_warnings_combined():
    yaml_str = """
alias: Test
trigger:
  - platform: state
    entity_id: light.unknown_entity
action:
  - service: bogus_domain.action
    target:
      entity_id: sensor.fake
"""
    result = validate(yaml_str, KNOWN_ENTITIES)
    assert result.valid is True
    assert len(result.issues) >= 3  # 2 entity + 1 service


def test_empty_yaml():
    result = validate("", KNOWN_ENTITIES)
    assert result.valid is False


def test_clean_automation():
    """A well-formed automation using only known entities and valid services."""
    yaml_str = """
alias: Temperature Alert
description: Notify when temperature is high
trigger:
  - platform: numeric_state
    entity_id: sensor.temperature
    above: 30
action:
  - service: light.turn_on
    target:
      entity_id: light.kitchen
    data:
      brightness: 255
      color_name: red
"""
    result = validate(yaml_str, KNOWN_ENTITIES)
    assert result.valid is True
    assert len(result.issues) == 0
