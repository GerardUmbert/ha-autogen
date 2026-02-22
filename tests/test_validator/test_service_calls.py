"""Tests for service call validation."""

from autogen.validator.service_calls import check_service_calls


def test_valid_service_calls():
    parsed = {
        "action": [
            {"service": "light.turn_on", "target": {"entity_id": "light.kitchen"}},
            {"service": "switch.turn_off", "target": {"entity_id": "switch.fan"}},
        ],
    }
    issues = check_service_calls(parsed)
    assert len(issues) == 0


def test_unknown_domain():
    parsed = {
        "action": [
            {"service": "foobar.do_thing"},
        ],
    }
    issues = check_service_calls(parsed)
    assert len(issues) == 1
    assert issues[0].check_name == "service_calls"
    assert issues[0].severity.value == "warning"
    assert "foobar" in issues[0].message
    assert issues[0].suggestion is not None


def test_malformed_service_no_dot():
    parsed = {
        "action": [
            {"service": "turn_on"},
        ],
    }
    issues = check_service_calls(parsed)
    assert len(issues) == 1
    assert "Malformed" in issues[0].message


def test_multiple_services_mixed():
    parsed = {
        "action": [
            {"service": "light.turn_on"},
            {"service": "badformat"},
            {"service": "unknown_domain.something"},
            {"service": "climate.set_temperature"},
        ],
    }
    issues = check_service_calls(parsed)
    assert len(issues) == 2  # malformed + unknown domain


def test_nested_service_calls():
    """Service calls inside choose/sequence blocks."""
    parsed = {
        "action": [
            {
                "choose": [
                    {
                        "sequence": [
                            {"service": "light.turn_on"},
                            {"service": "notify.mobile_app"},
                        ]
                    }
                ]
            }
        ],
    }
    issues = check_service_calls(parsed)
    assert len(issues) == 0


def test_no_service_calls():
    parsed = {
        "alias": "Test",
        "trigger": {"platform": "time", "at": "07:00:00"},
    }
    issues = check_service_calls(parsed)
    assert len(issues) == 0


def test_all_known_domains():
    """Spot-check that common HA domains are recognized."""
    domains = ["light", "switch", "automation", "climate", "cover",
               "media_player", "notify", "script", "scene", "vacuum",
               "lock", "fan", "camera", "input_boolean", "input_number"]
    for domain in domains:
        parsed = {"action": [{"service": f"{domain}.test_action"}]}
        issues = check_service_calls(parsed)
        assert len(issues) == 0, f"Domain '{domain}' should be recognized"
