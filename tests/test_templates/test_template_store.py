"""Tests for autogen.llm.prompts.templates — TemplateStore CRUD and prompt application."""

from __future__ import annotations

import pytest
import pytest_asyncio

from autogen.db.database import Database
from autogen.llm.prompts.templates import (
    PromptTemplate,
    TemplateStore,
    _sanitize_content,
    apply_templates,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db(tmp_path):
    """Create a temporary database with all migrations applied."""
    db = Database(db_path=str(tmp_path / "test.db"))
    await db.connect()
    yield db
    await db.close()


@pytest_asyncio.fixture
async def store(db):
    """Create a TemplateStore backed by the temporary database."""
    return TemplateStore(db.conn)


# ---------------------------------------------------------------------------
# CRUD tests
# ---------------------------------------------------------------------------

class TestTemplateStoreCRUD:
    @pytest.mark.asyncio
    async def test_create_and_get_template(self, store: TemplateStore) -> None:
        """Creating a template and retrieving it by ID should return the same data."""
        template = PromptTemplate(
            name="My Custom Rule",
            content="Always prefer YAML anchors for repeated values.",
            target="automation",
            position="append",
            enabled=True,
        )
        created = await store.create_template(template)

        assert created is not None
        assert created.name == "My Custom Rule"
        assert created.content == "Always prefer YAML anchors for repeated values."
        assert created.target == "automation"
        assert created.position == "append"
        assert created.enabled is True
        assert created.created_at != ""
        assert created.updated_at != ""

        # Fetch by ID
        fetched = await store.get_template(created.id)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.name == created.name

    @pytest.mark.asyncio
    async def test_list_templates(self, store: TemplateStore) -> None:
        """list_templates should return all templates ordered by name."""
        await store.create_template(PromptTemplate(name="Zebra Rule", content="Z content", target="system"))
        await store.create_template(PromptTemplate(name="Alpha Rule", content="A content", target="system"))
        await store.create_template(PromptTemplate(name="Middle Rule", content="M content", target="automation"))

        templates = await store.list_templates()
        assert len(templates) == 3
        names = [t.name for t in templates]
        assert names == ["Alpha Rule", "Middle Rule", "Zebra Rule"]

    @pytest.mark.asyncio
    async def test_update_template(self, store: TemplateStore) -> None:
        """Updating fields should persist the changes."""
        created = await store.create_template(
            PromptTemplate(name="Original Name", content="Original content", target="system")
        )
        assert created is not None
        original_updated_at = created.updated_at

        updated = await store.update_template(
            created.id,
            {"name": "Updated Name", "content": "Updated content", "enabled": False},
        )
        assert updated is not None
        assert updated.name == "Updated Name"
        assert updated.content == "Updated content"
        assert updated.enabled is False
        # updated_at should change (or at least not be empty)
        assert updated.updated_at != ""

    @pytest.mark.asyncio
    async def test_update_template_nonexistent(self, store: TemplateStore) -> None:
        """Updating a non-existent template should return None."""
        result = await store.update_template("nonexistent-id", {"name": "Foo"})
        assert result is None

    @pytest.mark.asyncio
    async def test_update_template_ignores_disallowed_fields(self, store: TemplateStore) -> None:
        """Fields not in the allowed set should be silently ignored."""
        created = await store.create_template(
            PromptTemplate(name="Test", content="Content", target="system")
        )
        assert created is not None

        updated = await store.update_template(
            created.id,
            {"name": "New Name", "id": "hacked-id", "created_at": "1970-01-01"},
        )
        assert updated is not None
        assert updated.name == "New Name"
        assert updated.id == created.id  # ID unchanged
        assert updated.created_at == created.created_at  # created_at unchanged

    @pytest.mark.asyncio
    async def test_delete_template(self, store: TemplateStore) -> None:
        """Deleting a template should remove it from the store."""
        created = await store.create_template(
            PromptTemplate(name="To Delete", content="Bye", target="system")
        )
        assert created is not None

        deleted = await store.delete_template(created.id)
        assert deleted is True

        # Should no longer exist
        fetched = await store.get_template(created.id)
        assert fetched is None

    @pytest.mark.asyncio
    async def test_delete_template_nonexistent(self, store: TemplateStore) -> None:
        """Deleting a non-existent template should return False."""
        result = await store.delete_template("does-not-exist")
        assert result is False


# ---------------------------------------------------------------------------
# Filtering tests
# ---------------------------------------------------------------------------

class TestTemplateStoreFiltering:
    @pytest.mark.asyncio
    async def test_get_active_templates_filters_by_target(self, store: TemplateStore) -> None:
        """get_active_templates should only return templates matching the target."""
        await store.create_template(
            PromptTemplate(name="Auto Rule", content="Automation hint", target="automation")
        )
        await store.create_template(
            PromptTemplate(name="Dash Rule", content="Dashboard hint", target="dashboard")
        )
        await store.create_template(
            PromptTemplate(name="Review Rule", content="Review hint", target="review")
        )

        auto_templates = await store.get_active_templates("automation")
        assert len(auto_templates) == 1
        assert auto_templates[0].name == "Auto Rule"

        dash_templates = await store.get_active_templates("dashboard")
        assert len(dash_templates) == 1
        assert dash_templates[0].name == "Dash Rule"

    @pytest.mark.asyncio
    async def test_get_active_templates_excludes_disabled(self, store: TemplateStore) -> None:
        """Disabled templates should not be returned by get_active_templates."""
        created = await store.create_template(
            PromptTemplate(name="Enabled Rule", content="Active", target="system", enabled=True)
        )
        disabled = await store.create_template(
            PromptTemplate(name="Disabled Rule", content="Inactive", target="system", enabled=False)
        )

        active = await store.get_active_templates("system")
        assert len(active) == 1
        assert active[0].name == "Enabled Rule"

    @pytest.mark.asyncio
    async def test_get_active_templates_empty(self, store: TemplateStore) -> None:
        """When no templates match, return an empty list."""
        active = await store.get_active_templates("system")
        assert active == []


# ---------------------------------------------------------------------------
# apply_templates
# ---------------------------------------------------------------------------

class TestApplyTemplates:
    def test_apply_templates_append(self) -> None:
        """Append templates should be added after the base prompt."""
        templates = [
            PromptTemplate(name="Footer", content="Always end with a summary.", target="system", position="append"),
        ]
        result = apply_templates("Base system prompt.", templates)
        assert result == "Base system prompt.\n\nAlways end with a summary."

    def test_apply_templates_prepend(self) -> None:
        """Prepend templates should be added before the base prompt."""
        templates = [
            PromptTemplate(name="Header", content="IMPORTANT CONTEXT:", target="system", position="prepend"),
        ]
        result = apply_templates("Base system prompt.", templates)
        assert result == "IMPORTANT CONTEXT:\n\nBase system prompt."

    def test_apply_templates_mixed(self) -> None:
        """A mix of prepend and append templates should wrap the base prompt."""
        templates = [
            PromptTemplate(name="Header", content="## Preamble", target="system", position="prepend"),
            PromptTemplate(name="Footer", content="## Closing notes", target="system", position="append"),
            PromptTemplate(name="Second Prepend", content="## Extra Context", target="system", position="prepend"),
        ]
        result = apply_templates("Base prompt.", templates)

        # Prepends come first (in order), then base, then appends
        assert result == "## Preamble\n\n## Extra Context\n\nBase prompt.\n\n## Closing notes"

    def test_apply_templates_empty(self) -> None:
        """With no templates, the base prompt is returned unchanged."""
        result = apply_templates("Base prompt only.", [])
        assert result == "Base prompt only."


# ---------------------------------------------------------------------------
# _sanitize_content
# ---------------------------------------------------------------------------

class TestSanitizeContent:
    def test_sanitize_content_strips_code_fences(self) -> None:
        """Markdown code fences should be removed from content."""
        content = "```yaml\nsome: yaml\n```"
        result = _sanitize_content(content)
        assert "```" not in result
        assert "some: yaml" in result

    def test_sanitize_content_strips_language_tag(self) -> None:
        """Code fences with language tags (```python) should be stripped."""
        content = "```python\nprint('hello')\n```"
        result = _sanitize_content(content)
        assert "```" not in result
        assert "print('hello')" in result

    def test_sanitize_content_max_length(self) -> None:
        """Content exceeding MAX_TEMPLATE_CONTENT (2000) should be truncated."""
        content = "x" * 3000
        result = _sanitize_content(content)
        assert len(result) == 2000

    def test_sanitize_content_strips_whitespace(self) -> None:
        """Leading/trailing whitespace should be stripped."""
        content = "   some content   "
        result = _sanitize_content(content)
        assert result == "some content"

    def test_sanitize_content_normal_text(self) -> None:
        """Normal text without code fences should pass through unchanged (minus strip)."""
        content = "Just a normal instruction for the LLM."
        result = _sanitize_content(content)
        assert result == "Just a normal instruction for the LLM."
