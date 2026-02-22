"""Tests for autogen.reviewer.scoping — entity extraction and area-based filtering."""

from __future__ import annotations

import pytest

from autogen.reviewer.scoping import (
    extract_entity_ids_from_automation,
    filter_automations_by_area,
    filter_dashboard_view_by_path,
    filter_dashboard_views_by_area,
)


# ---------------------------------------------------------------------------
# extract_entity_ids_from_automation
# ---------------------------------------------------------------------------

class TestExtractEntityIds:
    def test_extract_entity_ids_simple(self) -> None:
        """A trigger with a single entity_id string should be extracted."""
        automation = {
            "alias": "Motion Light",
            "trigger": [
                {
                    "platform": "state",
                    "entity_id": "binary_sensor.motion_kitchen",
                    "to": "on",
                }
            ],
            "action": [
                {
                    "service": "light.turn_on",
                    "target": {"entity_id": "light.kitchen_ceiling"},
                }
            ],
        }
        result = extract_entity_ids_from_automation(automation)
        assert result == {"binary_sensor.motion_kitchen", "light.kitchen_ceiling"}

    def test_extract_entity_ids_nested_list(self) -> None:
        """entity_id as a list should extract all entries."""
        automation = {
            "trigger": [
                {
                    "platform": "state",
                    "entity_id": [
                        "binary_sensor.motion_living_room",
                        "binary_sensor.motion_hallway",
                    ],
                }
            ],
            "action": [
                {
                    "service": "light.turn_on",
                    "target": {
                        "entity_id": ["light.living_room", "light.hallway"],
                    },
                }
            ],
        }
        result = extract_entity_ids_from_automation(automation)
        assert result == {
            "binary_sensor.motion_living_room",
            "binary_sensor.motion_hallway",
            "light.living_room",
            "light.hallway",
        }

    def test_extract_entity_ids_entities_key(self) -> None:
        """Lovelace-style 'entities' list with string items and dict items."""
        card = {
            "type": "entities",
            "entities": [
                "sensor.temperature_bedroom",
                "sensor.humidity_bedroom",
                {"entity": "light.bedroom_lamp", "name": "Lamp"},
            ],
        }
        result = extract_entity_ids_from_automation(card)
        assert result == {
            "sensor.temperature_bedroom",
            "sensor.humidity_bedroom",
            "light.bedroom_lamp",
        }

    def test_extract_entity_ids_empty(self) -> None:
        """An empty automation dict should return an empty set."""
        assert extract_entity_ids_from_automation({}) == set()

    def test_extract_entity_ids_deeply_nested(self) -> None:
        """Entity IDs buried in deeply nested choose/sequence actions."""
        automation = {
            "action": [
                {
                    "choose": [
                        {
                            "conditions": [
                                {
                                    "condition": "state",
                                    "entity_id": "binary_sensor.door_front",
                                    "state": "on",
                                }
                            ],
                            "sequence": [
                                {
                                    "service": "lock.lock",
                                    "target": {"entity_id": "lock.front_door"},
                                }
                            ],
                        }
                    ]
                }
            ],
        }
        result = extract_entity_ids_from_automation(automation)
        assert "binary_sensor.door_front" in result
        assert "lock.front_door" in result


# ---------------------------------------------------------------------------
# filter_automations_by_area
# ---------------------------------------------------------------------------

class TestFilterAutomationsByArea:
    def test_filter_automations_by_area_found(self) -> None:
        """Automations referencing entities in the target area should be returned."""
        automations = [
            {
                "alias": "Kitchen Motion Light",
                "trigger": [{"platform": "state", "entity_id": "binary_sensor.motion_kitchen"}],
                "action": [{"service": "light.turn_on", "target": {"entity_id": "light.kitchen_ceiling"}}],
            },
            {
                "alias": "Bedroom Night Mode",
                "trigger": [{"platform": "time", "at": "22:00"}],
                "action": [{"service": "light.turn_off", "target": {"entity_id": "light.bedroom_main"}}],
            },
        ]
        entity_area_map = {
            "binary_sensor.motion_kitchen": "kitchen",
            "light.kitchen_ceiling": "kitchen",
            "light.bedroom_main": "bedroom",
        }

        result = filter_automations_by_area(automations, "kitchen", entity_area_map)
        assert len(result) == 1
        assert result[0]["alias"] == "Kitchen Motion Light"

    def test_filter_automations_by_area_none(self) -> None:
        """When no automations match the area, return an empty list."""
        automations = [
            {
                "alias": "Garage Door",
                "trigger": [{"platform": "state", "entity_id": "binary_sensor.garage_door"}],
                "action": [{"service": "cover.open_cover", "target": {"entity_id": "cover.garage"}}],
            },
        ]
        entity_area_map = {
            "binary_sensor.garage_door": "garage",
            "cover.garage": "garage",
        }

        result = filter_automations_by_area(automations, "kitchen", entity_area_map)
        assert result == []

    def test_filter_automations_by_area_multiple_matches(self) -> None:
        """Multiple automations referencing the same area should all be returned."""
        automations = [
            {
                "alias": "Living Room Motion",
                "action": [{"service": "light.turn_on", "target": {"entity_id": "light.living_room"}}],
            },
            {
                "alias": "Living Room Temperature Alert",
                "trigger": [{"platform": "numeric_state", "entity_id": "sensor.temperature_living_room"}],
                "action": [{"service": "notify.notify"}],
            },
        ]
        entity_area_map = {
            "light.living_room": "living_room",
            "sensor.temperature_living_room": "living_room",
        }

        result = filter_automations_by_area(automations, "living_room", entity_area_map)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# filter_dashboard_views_by_area
# ---------------------------------------------------------------------------

class TestFilterDashboardViewsByArea:
    def test_filter_dashboard_views_by_area_title_match(self) -> None:
        """A view whose title contains the area name should match."""
        dashboard = {
            "views": [
                {"title": "Kitchen Overview", "cards": []},
                {"title": "Bedroom Overview", "cards": []},
                {"title": "Home", "cards": []},
            ]
        }
        entity_area_map: dict[str, str | None] = {}
        area_names = {"kitchen": "Kitchen", "bedroom": "Bedroom"}

        result = filter_dashboard_views_by_area(dashboard, "kitchen", entity_area_map, area_names)
        assert len(result["views"]) == 1
        assert result["views"][0]["title"] == "Kitchen Overview"

    def test_filter_dashboard_views_by_area_entity_match(self) -> None:
        """A view with cards referencing entities in the area should match."""
        dashboard = {
            "views": [
                {
                    "title": "General",
                    "cards": [
                        {
                            "type": "entities",
                            "entities": [
                                "light.kitchen_ceiling",
                                "sensor.temperature_kitchen",
                            ],
                        }
                    ],
                },
                {
                    "title": "Other",
                    "cards": [
                        {
                            "type": "entities",
                            "entities": ["light.bedroom_main"],
                        }
                    ],
                },
            ]
        }
        entity_area_map = {
            "light.kitchen_ceiling": "kitchen",
            "sensor.temperature_kitchen": "kitchen",
            "light.bedroom_main": "bedroom",
        }
        area_names = {"kitchen": "Kitchen", "bedroom": "Bedroom"}

        result = filter_dashboard_views_by_area(dashboard, "kitchen", entity_area_map, area_names)
        assert len(result["views"]) == 1
        assert result["views"][0]["title"] == "General"

    def test_filter_dashboard_views_by_area_no_match(self) -> None:
        """When no views match the area, return empty views list."""
        dashboard = {
            "views": [
                {"title": "Home", "cards": []},
            ]
        }
        entity_area_map: dict[str, str | None] = {}
        area_names = {"kitchen": "Kitchen"}

        result = filter_dashboard_views_by_area(dashboard, "kitchen", entity_area_map, area_names)
        assert result["views"] == []


# ---------------------------------------------------------------------------
# filter_dashboard_view_by_path
# ---------------------------------------------------------------------------

class TestFilterDashboardViewByPath:
    def test_filter_dashboard_view_by_path_exact(self) -> None:
        """Exact path match should return that single view."""
        dashboard = {
            "views": [
                {"path": "kitchen", "title": "Kitchen", "cards": []},
                {"path": "bedroom", "title": "Bedroom", "cards": []},
                {"path": "living-room", "title": "Living Room", "cards": []},
            ]
        }
        result = filter_dashboard_view_by_path(dashboard, "bedroom")
        assert len(result["views"]) == 1
        assert result["views"][0]["title"] == "Bedroom"

    def test_filter_dashboard_view_by_path_index_fallback(self) -> None:
        """When no path matches, 'view-N' should fall back to index N."""
        dashboard = {
            "views": [
                {"title": "First View", "cards": []},
                {"title": "Second View", "cards": []},
                {"title": "Third View", "cards": []},
            ]
        }
        result = filter_dashboard_view_by_path(dashboard, "view-1")
        assert len(result["views"]) == 1
        assert result["views"][0]["title"] == "Second View"

    def test_filter_dashboard_view_by_path_index_zero(self) -> None:
        """view-0 should return the first view."""
        dashboard = {
            "views": [
                {"title": "Main Dashboard", "cards": []},
                {"title": "Settings", "cards": []},
            ]
        }
        result = filter_dashboard_view_by_path(dashboard, "view-0")
        assert len(result["views"]) == 1
        assert result["views"][0]["title"] == "Main Dashboard"

    def test_filter_dashboard_view_by_path_not_found(self) -> None:
        """An unmatched path (and non-view-N pattern) should return empty views."""
        dashboard = {
            "views": [
                {"path": "home", "title": "Home", "cards": []},
            ]
        }
        result = filter_dashboard_view_by_path(dashboard, "nonexistent")
        assert result["views"] == []

    def test_filter_dashboard_view_by_path_out_of_range(self) -> None:
        """view-N where N is out of range should return empty views."""
        dashboard = {
            "views": [
                {"title": "Only View", "cards": []},
            ]
        }
        result = filter_dashboard_view_by_path(dashboard, "view-5")
        assert result["views"] == []
