"""Tests for the review engine (with mocked LLM)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from autogen.llm.base import LLMResponse
from autogen.reviewer.engine import ReviewEngine
from autogen.reviewer.models import FindingCategory, FindingSeverity


def _mock_llm(findings_json: list[dict] | None = None) -> AsyncMock:
    """Create a mock LLM backend that returns findings JSON."""
    mock = AsyncMock()
    if findings_json is None:
        findings_json = []
    content = "```json\n" + json.dumps(findings_json) + "\n```"
    mock.generate.return_value = LLMResponse(
        content=content,
        model="test-model",
        prompt_tokens=100,
        completion_tokens=50,
    )
    return mock


SAMPLE_AUTOMATIONS = [
    {
        "id": "auto_1",
        "alias": "Motion Light",
        "trigger": [{"platform": "state", "entity_id": "binary_sensor.motion"}],
        "condition": [{"condition": "sun", "after": "sunset"}],
        "action": [{"service": "light.turn_on", "target": {"entity_id": "light.hall"}}],
    },
    {
        "id": "auto_2",
        "alias": "Lock Door at Night",
        "trigger": [{"platform": "time", "at": "23:00:00"}],
        "action": [{"service": "lock.lock", "target": {"entity_id": "lock.front"}}],
    },
]


@pytest.mark.asyncio
async def test_review_runs_both_rules_and_llm() -> None:
    llm_findings = [
        {
            "severity": "info",
            "category": "error_resilience",
            "automation_id": "auto_1",
            "automation_alias": "Motion Light",
            "title": "No timeout on action",
            "description": "Consider adding a timeout.",
        }
    ]
    mock_llm = _mock_llm(llm_findings)
    engine = ReviewEngine(mock_llm)

    result = await engine.review_automations(SAMPLE_AUTOMATIONS)

    # Should have deterministic findings (auto_2 has lock without conditions = critical)
    # plus the LLM finding
    assert result.automations_reviewed == 2
    assert len(result.findings) > 0

    categories = {f.category for f in result.findings}
    assert FindingCategory.security in categories  # from deterministic rules
    assert FindingCategory.error_resilience in categories  # from LLM

    assert result.model == "test-model"


@pytest.mark.asyncio
async def test_review_llm_failure_falls_back_to_rules() -> None:
    mock_llm = AsyncMock()
    mock_llm.generate.side_effect = RuntimeError("LLM offline")
    engine = ReviewEngine(mock_llm)

    result = await engine.review_automations(SAMPLE_AUTOMATIONS)

    # Should still have deterministic findings
    assert len(result.findings) > 0
    assert result.model == ""  # LLM didn't respond


@pytest.mark.asyncio
async def test_review_deduplicates_findings() -> None:
    # LLM returns same finding that rules already found
    llm_findings = [
        {
            "severity": "critical",
            "category": "security",
            "automation_id": "auto_2",
            "automation_alias": "Lock Door at Night",
            "title": "Sensitive domain without adequate guards: lock",
            "description": "Lock without conditions",
        }
    ]
    mock_llm = _mock_llm(llm_findings)
    engine = ReviewEngine(mock_llm)

    result = await engine.review_automations(SAMPLE_AUTOMATIONS)

    # Should not have duplicate security findings for auto_2
    security_findings_auto2 = [
        f for f in result.findings
        if f.category == FindingCategory.security and f.automation_id == "auto_2"
    ]
    assert len(security_findings_auto2) == 1  # deduped


@pytest.mark.asyncio
async def test_review_summary_format() -> None:
    mock_llm = _mock_llm([])
    engine = ReviewEngine(mock_llm)

    result = await engine.review_automations(SAMPLE_AUTOMATIONS)

    assert "2 automation(s)" in result.summary
    assert "issue(s)" in result.summary or "no issues" in result.summary.lower()


@pytest.mark.asyncio
async def test_review_clean_automation_few_findings() -> None:
    clean_auto = [
        {
            "id": "clean_1",
            "alias": "Clean Automation",
            "trigger": [{"platform": "state", "entity_id": "binary_sensor.door"}],
            "condition": [{"condition": "time", "after": "08:00", "before": "22:00"}],
            "action": [{"service": "light.turn_on", "target": {"entity_id": "light.hall"}}],
        }
    ]
    mock_llm = _mock_llm([])
    engine = ReviewEngine(mock_llm)

    result = await engine.review_automations(clean_auto)

    # Clean automation with conditions — no deterministic findings expected
    assert len(result.findings) == 0
