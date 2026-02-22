"""Tests for autogen.explorer.analysis — inventory analysis and pattern matching."""

from __future__ import annotations

import pytest

from autogen.context.areas import AreaEntry
from autogen.context.entities import EntityEntry
from autogen.explorer.analysis import (
    analyze_inventory,
    extract_automated_entities,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _entity(
    entity_id: str,
    name: str | None = None,
    area_id: str | None = None,
    disabled_by: str | None = None,
    hidden_by: str | None = None,
) -> EntityEntry:
    """Create an EntityEntry for testing."""
    return EntityEntry(
        entity_id=entity_id,
        name=name,
        platform="test",
        device_id=None,
        area_id=area_id,
        disabled_by=disabled_by,
        hidden_by=hidden_by,
        labels=[],
    )


def _area(area_id: str, name: str) -> AreaEntry:
    """Create an AreaEntry for testing."""
    return AreaEntry(
        area_id=area_id,
        name=name,
        aliases=[],
        floor_id=None,
        icon=None,
        labels=[],
        picture=None,
    )


# ---------------------------------------------------------------------------
# extract_automated_entities
# ---------------------------------------------------------------------------

class TestExtractAutomatedEntities:
    def test_extract_automated_entities_basic(self) -> None:
        """Entity IDs from triggers, conditions, and actions should all be extracted."""
        automations = [
            {
                "alias": "Kitchen Motion",
                "trigger": [
                    {"platform": "state", "entity_id": "binary_sensor.motion_kitchen", "to": "on"}
                ],
                "action": [
                    {"service": "light.turn_on", "target": {"entity_id": "light.kitchen_ceiling"}}
                ],
            },
            {
                "alias": "Bedroom Night",
                "trigger": [
                    {"platform": "time", "at": "22:00"}
                ],
                "condition": [
                    {"condition": "state", "entity_id": "binary_sensor.bedroom_occupancy", "state": "on"}
                ],
                "action": [
                    {"service": "light.turn_off", "target": {"entity_id": "light.bedroom_main"}}
                ],
            },
        ]
        result = extract_automated_entities(automations)
        assert result == {
            "binary_sensor.motion_kitchen",
            "light.kitchen_ceiling",
            "binary_sensor.bedroom_occupancy",
            "light.bedroom_main",
        }

    def test_extract_automated_entities_empty(self) -> None:
        """An empty automations list should return an empty set."""
        assert extract_automated_entities([]) == set()

    def test_extract_automated_entities_no_entity_ids(self) -> None:
        """Automations without entity references should return empty set."""
        automations = [
            {
                "alias": "Time-based",
                "trigger": [{"platform": "time", "at": "08:00"}],
                "action": [{"service": "notify.notify", "data": {"message": "Good morning"}}],
            }
        ]
        assert extract_automated_entities(automations) == set()


# ---------------------------------------------------------------------------
# analyze_inventory
# ---------------------------------------------------------------------------

class TestAnalyzeInventory:
    def test_analyze_inventory_basic(self) -> None:
        """Basic analysis with entities across areas, some automated."""
        entities = [
            _entity("light.living_room", "Living Room Light", area_id="living_room"),
            _entity("light.kitchen_ceiling", "Kitchen Ceiling", area_id="kitchen"),
            _entity("binary_sensor.motion_kitchen", "Kitchen Motion", area_id="kitchen"),
            _entity("sensor.temperature_bedroom", "Bedroom Temp", area_id="bedroom"),
            _entity("switch.garage_door", "Garage Door", area_id="garage"),
        ]
        areas = [
            _area("living_room", "Living Room"),
            _area("kitchen", "Kitchen"),
            _area("bedroom", "Bedroom"),
            _area("garage", "Garage"),
        ]
        automations = [
            {
                "alias": "Kitchen Motion",
                "trigger": [{"platform": "state", "entity_id": "binary_sensor.motion_kitchen"}],
                "action": [{"service": "light.turn_on", "target": {"entity_id": "light.kitchen_ceiling"}}],
            },
        ]

        result = analyze_inventory(entities, areas, automations)

        assert result.total_entities == 5
        assert result.total_areas == 4
        assert result.total_automations == 1
        assert "binary_sensor.motion_kitchen" in result.automated_entity_ids
        assert "light.kitchen_ceiling" in result.automated_entity_ids
        assert "light.living_room" in result.unautomated_entity_ids
        assert "sensor.temperature_bedroom" in result.unautomated_entity_ids
        assert "switch.garage_door" in result.unautomated_entity_ids

    def test_analyze_inventory_pattern_matching(self) -> None:
        """A motion sensor + light in the same area should trigger the motion-light pattern."""
        entities = [
            _entity("binary_sensor.motion_hallway", "Hallway Motion", area_id="hallway"),
            _entity("light.hallway_ceiling", "Hallway Light", area_id="hallway"),
        ]
        areas = [_area("hallway", "Hallway")]
        automations: list[dict] = []  # No existing automations

        result = analyze_inventory(entities, areas, automations)

        # Should find the "Turn lights on/off with motion" pattern
        assert len(result.matched_patterns) >= 1
        pattern_titles = [p.title for p in result.matched_patterns]
        assert "Turn lights on/off with motion" in pattern_titles

        # Check the pattern has the correct entities
        motion_pattern = next(p for p in result.matched_patterns if p.title == "Turn lights on/off with motion")
        assert motion_pattern.area_id == "hallway"
        assert motion_pattern.area_name == "Hallway"
        assert "binary_sensor.motion_hallway" in motion_pattern.trigger_entities
        assert "light.hallway_ceiling" in motion_pattern.target_entities

    def test_analyze_inventory_coverage_calculation(self) -> None:
        """Coverage should be (automated / total) * 100."""
        entities = [
            _entity("light.living_room", "Living Room Light", area_id="living_room"),
            _entity("light.bedroom", "Bedroom Light", area_id="bedroom"),
            _entity("sensor.temperature_living", "Living Temp", area_id="living_room"),
            _entity("binary_sensor.motion_living", "Living Motion", area_id="living_room"),
        ]
        areas = [
            _area("living_room", "Living Room"),
            _area("bedroom", "Bedroom"),
        ]
        # Automate 2 out of 4 entities -> 50%
        automations = [
            {
                "trigger": [{"platform": "state", "entity_id": "binary_sensor.motion_living"}],
                "action": [{"service": "light.turn_on", "target": {"entity_id": "light.living_room"}}],
            }
        ]

        result = analyze_inventory(entities, areas, automations)
        assert result.coverage_percent == pytest.approx(50.0)

    def test_analyze_inventory_empty(self) -> None:
        """With no entities, areas, or automations, analysis should be zeroed out."""
        result = analyze_inventory([], [], [])

        assert result.total_entities == 0
        assert result.total_areas == 0
        assert result.total_automations == 0
        assert result.automated_entity_ids == set()
        assert result.unautomated_entity_ids == set()
        assert result.area_profiles == []
        assert result.matched_patterns == []
        assert result.coverage_percent == 0.0

    def test_analyze_inventory_skips_disabled_entities(self) -> None:
        """Disabled entities should not be counted in totals or patterns."""
        entities = [
            _entity("light.living_room", "Living Room Light", area_id="living_room"),
            _entity("light.disabled_light", "Disabled Light", area_id="living_room", disabled_by="user"),
            _entity("binary_sensor.motion_living", "Motion Living", area_id="living_room"),
            _entity("sensor.hidden_sensor", "Hidden Sensor", area_id="living_room", hidden_by="integration"),
        ]
        areas = [_area("living_room", "Living Room")]
        automations: list[dict] = []

        result = analyze_inventory(entities, areas, automations)

        # Only 2 active entities (disabled and hidden excluded)
        assert result.total_entities == 2
        assert "light.disabled_light" not in result.unautomated_entity_ids
        assert "sensor.hidden_sensor" not in result.unautomated_entity_ids
        assert "light.living_room" in result.unautomated_entity_ids
        assert "binary_sensor.motion_living" in result.unautomated_entity_ids

    def test_analyze_inventory_pattern_not_matched_when_all_automated(self) -> None:
        """Patterns should not appear if all entities in the pattern are already automated."""
        entities = [
            _entity("binary_sensor.motion_kitchen", "Kitchen Motion", area_id="kitchen"),
            _entity("light.kitchen_ceiling", "Kitchen Light", area_id="kitchen"),
        ]
        areas = [_area("kitchen", "Kitchen")]
        automations = [
            {
                "trigger": [{"platform": "state", "entity_id": "binary_sensor.motion_kitchen"}],
                "action": [{"service": "light.turn_on", "target": {"entity_id": "light.kitchen_ceiling"}}],
            }
        ]

        result = analyze_inventory(entities, areas, automations)

        # All entities are automated, so no "Turn lights on/off with motion" pattern
        motion_patterns = [p for p in result.matched_patterns if p.title == "Turn lights on/off with motion"]
        assert len(motion_patterns) == 0

    def test_analyze_inventory_multiple_areas_with_patterns(self) -> None:
        """Multiple areas with pattern-matching entity pairs should produce multiple patterns."""
        entities = [
            # Kitchen: binary_sensor + light
            _entity("binary_sensor.motion_kitchen", "Kitchen Motion", area_id="kitchen"),
            _entity("light.kitchen_ceiling", "Kitchen Light", area_id="kitchen"),
            # Living Room: sensor + climate
            _entity("sensor.temperature_living", "Living Temp", area_id="living_room"),
            _entity("climate.living_thermostat", "Living Thermostat", area_id="living_room"),
            # Bedroom: no pattern (only one domain)
            _entity("light.bedroom_lamp", "Bedroom Lamp", area_id="bedroom"),
        ]
        areas = [
            _area("kitchen", "Kitchen"),
            _area("living_room", "Living Room"),
            _area("bedroom", "Bedroom"),
        ]
        automations: list[dict] = []

        result = analyze_inventory(entities, areas, automations)

        # Should find patterns in kitchen and living room, but not bedroom
        pattern_areas = {p.area_id for p in result.matched_patterns}
        assert "kitchen" in pattern_areas
        assert "living_room" in pattern_areas
        assert "bedroom" not in pattern_areas

    def test_analyze_inventory_area_profiles_sorted_by_patterns(self) -> None:
        """Area profiles should be sorted by number of potential patterns (descending)."""
        entities = [
            # Rich area: multiple domains -> many patterns
            _entity("binary_sensor.motion_rich", "Rich Motion", area_id="rich"),
            _entity("light.rich_light", "Rich Light", area_id="rich"),
            _entity("switch.rich_switch", "Rich Switch", area_id="rich"),
            _entity("sensor.rich_temp", "Rich Temp", area_id="rich"),
            _entity("climate.rich_climate", "Rich Climate", area_id="rich"),
            # Simple area: one domain -> no patterns
            _entity("light.simple_light", "Simple Light", area_id="simple"),
        ]
        areas = [
            _area("rich", "Rich Room"),
            _area("simple", "Simple Room"),
        ]
        automations: list[dict] = []

        result = analyze_inventory(entities, areas, automations)

        # Rich room should come first (more patterns)
        assert len(result.area_profiles) >= 1
        assert result.area_profiles[0].area_id == "rich"
