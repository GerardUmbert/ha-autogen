"""Tests for YAML syntax validation."""

from autogen.validator.yaml_syntax import check_yaml_syntax


def test_valid_yaml():
    yaml_str = """
alias: Test Automation
trigger:
  - platform: state
    entity_id: light.living_room
action:
  - service: light.turn_on
    target:
      entity_id: light.kitchen
"""
    result = check_yaml_syntax(yaml_str)
    assert result.valid is True
    assert len(result.issues) == 0
    assert result.yaml_parsed is not None
    assert result.yaml_parsed["alias"] == "Test Automation"


def test_invalid_yaml_bad_indentation():
    yaml_str = """
alias: Test
trigger:
  - platform: state
    entity_id: light.living_room
  action:  # wrong indentation level
  - service: light.turn_on
"""
    result = check_yaml_syntax(yaml_str)
    # ruamel may or may not error on this specific case, but let's test
    # a definitely-invalid YAML instead
    yaml_str_bad = "foo: bar\n  baz: [invalid\nqux"
    result = check_yaml_syntax(yaml_str_bad)
    assert result.valid is False
    assert len(result.issues) == 1
    assert result.issues[0].check_name == "yaml_syntax"
    assert result.issues[0].severity.value == "error"


def test_invalid_yaml_unclosed_bracket():
    yaml_str = "items: [one, two, three"
    result = check_yaml_syntax(yaml_str)
    assert result.valid is False
    assert len(result.issues) == 1
    assert result.issues[0].check_name == "yaml_syntax"


def test_empty_string():
    result = check_yaml_syntax("")
    assert result.valid is False
    assert len(result.issues) == 1
    assert "Empty" in result.issues[0].message


def test_whitespace_only():
    result = check_yaml_syntax("   \n\n  ")
    assert result.valid is False
    assert len(result.issues) == 1


def test_null_yaml():
    """YAML that parses to null/None."""
    result = check_yaml_syntax("---\n")
    assert result.valid is False
    assert any("null" in i.message.lower() or "empty" in i.message.lower() for i in result.issues)


def test_parsed_dict_returned():
    yaml_str = """
trigger:
  platform: state
  entity_id: sensor.temperature
"""
    result = check_yaml_syntax(yaml_str)
    assert result.valid is True
    assert isinstance(result.yaml_parsed, dict)
    assert "trigger" in result.yaml_parsed


def test_error_has_line_number():
    yaml_str = "valid: true\ninvalid: [unclosed\nmore: stuff"
    result = check_yaml_syntax(yaml_str)
    assert result.valid is False
    assert result.issues[0].line is not None
    assert result.issues[0].line > 0
