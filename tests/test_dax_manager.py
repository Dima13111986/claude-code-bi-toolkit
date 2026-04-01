"""Tests for DAX Snippet Manager (scripts/dax_manager.py).

Uses tmp_path fixture for isolated JSON storage — never touches real data/.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Adjust sys.path so we can import from scripts/
# ---------------------------------------------------------------------------
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from dax_manager import DAXManager, _slugify


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def storage_path(tmp_path: Path) -> Path:
    """Return a temporary path for the JSON storage file."""
    return tmp_path / "dax_snippets.json"


@pytest.fixture()
def manager(storage_path: Path) -> DAXManager:
    """Return a DAXManager with default pre-populated snippets."""
    return DAXManager(storage_path=storage_path)


@pytest.fixture()
def empty_manager(tmp_path: Path) -> DAXManager:
    """Return a DAXManager with an empty snippet list."""
    path = tmp_path / "empty_snippets.json"
    path.write_text(
        json.dumps({"version": "1.0.0", "snippets": []}, indent=2),
        encoding="utf-8",
    )
    return DAXManager(storage_path=path)


# ---------------------------------------------------------------------------
# Slugify
# ---------------------------------------------------------------------------

class TestSlugify:
    """Tests for the _slugify helper function."""

    def test_basic(self) -> None:
        assert _slugify("YTD Sales") == "ytd-sales"

    def test_special_chars(self) -> None:
        assert _slugify("% of Grand Total") == "of-grand-total"

    def test_multiple_spaces(self) -> None:
        assert _slugify("  Moving  Average  3M  ") == "moving-average-3m"

    def test_already_slug(self) -> None:
        assert _slugify("safe-divide") == "safe-divide"


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

class TestInit:
    """Tests for DAXManager initialization and storage creation."""

    def test_creates_storage_file(self, storage_path: Path, manager: DAXManager) -> None:
        assert storage_path.exists()

    def test_default_snippets_count(self, manager: DAXManager) -> None:
        assert len(manager.snippets) == 10

    def test_storage_valid_json(self, storage_path: Path, manager: DAXManager) -> None:
        data = json.loads(storage_path.read_text(encoding="utf-8"))
        assert "version" in data
        assert "snippets" in data

    def test_all_snippets_have_required_fields(self, manager: DAXManager) -> None:
        required = {"id", "name", "category", "description", "dax", "tags", "created", "modified"}
        for s in manager.snippets:
            assert required.issubset(s.keys()), f"Missing fields in {s['id']}"


# ---------------------------------------------------------------------------
# Add
# ---------------------------------------------------------------------------

class TestAdd:
    """Tests for the 'add' subcommand."""

    def test_add_new_snippet(self, manager: DAXManager) -> None:
        snippet = manager.add(
            name="Test Measure",
            dax="VAR _x = SUM(Sales[Amount])\nRETURN _x",
            category="custom",
            tags=["test"],
            description="A test measure",
        )
        assert snippet["id"] == "test-measure"
        assert snippet["name"] == "Test Measure"
        assert len(manager.snippets) == 11

    def test_add_persists_to_disk(self, manager: DAXManager, storage_path: Path) -> None:
        manager.add(name="Persisted", dax="VAR _x = 1\nRETURN _x")
        data = json.loads(storage_path.read_text(encoding="utf-8"))
        ids = [s["id"] for s in data["snippets"]]
        assert "persisted" in ids

    def test_add_duplicate_raises(self, manager: DAXManager) -> None:
        manager.add(name="Unique Name", dax="VAR _x = 1\nRETURN _x")
        with pytest.raises(ValueError, match="already exists"):
            manager.add(name="Unique Name", dax="VAR _y = 2\nRETURN _y")

    def test_add_duplicate_slug_raises(self, manager: DAXManager) -> None:
        """'YTD Sales' already exists from defaults."""
        with pytest.raises(ValueError, match="already exists"):
            manager.add(name="YTD Sales", dax="VAR _x = 1\nRETURN _x")

    def test_add_default_category(self, manager: DAXManager) -> None:
        snippet = manager.add(name="No Category", dax="VAR _x = 1\nRETURN _x")
        assert snippet["category"] == "general"


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

class TestSearch:
    """Tests for the 'search' subcommand."""

    def test_search_by_name(self, manager: DAXManager) -> None:
        results = manager.search("YTD")
        assert len(results) >= 1
        assert any("YTD" in s["name"] for s in results)

    def test_search_by_tag(self, manager: DAXManager) -> None:
        results = manager.search("fiscal")
        assert len(results) >= 1

    def test_search_by_partial_match(self, manager: DAXManager) -> None:
        results = manager.search("running")
        assert len(results) >= 1

    def test_search_by_dax_content(self, manager: DAXManager) -> None:
        results = manager.search("SAMEPERIODLASTYEAR")
        assert len(results) >= 1

    def test_search_no_results(self, manager: DAXManager) -> None:
        results = manager.search("xyznonexistent")
        assert results == []

    def test_search_case_insensitive(self, manager: DAXManager) -> None:
        results_lower = manager.search("ytd")
        results_upper = manager.search("YTD")
        assert len(results_lower) == len(results_upper)

    def test_search_empty_db(self, empty_manager: DAXManager) -> None:
        results = empty_manager.search("anything")
        assert results == []


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

class TestList:
    """Tests for the 'list' subcommand."""

    def test_list_all(self, manager: DAXManager) -> None:
        snippets = manager.list_snippets()
        assert len(snippets) == 10

    def test_list_by_category(self, manager: DAXManager) -> None:
        snippets = manager.list_snippets(category="time-intelligence")
        assert len(snippets) >= 2
        assert all(s["category"] == "time-intelligence" for s in snippets)

    def test_list_nonexistent_category(self, manager: DAXManager) -> None:
        snippets = manager.list_snippets(category="nonexistent")
        assert snippets == []

    def test_list_empty_db(self, empty_manager: DAXManager) -> None:
        snippets = empty_manager.list_snippets()
        assert snippets == []


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

class TestExport:
    """Tests for the 'export' subcommand."""

    def test_export_markdown_content(self, manager: DAXManager) -> None:
        content = manager.export(fmt="markdown")
        assert "# DAX Snippet Reference" in content
        assert "YTD Sales" in content
        assert "```dax" in content

    def test_export_json_valid(self, manager: DAXManager) -> None:
        content = manager.export(fmt="json")
        data = json.loads(content)
        assert isinstance(data, list)
        assert len(data) == 10

    def test_export_to_file(self, manager: DAXManager, tmp_path: Path) -> None:
        output = tmp_path / "export" / "reference.md"
        manager.export(fmt="markdown", output_path=output)
        assert output.exists()
        text = output.read_text(encoding="utf-8")
        assert "# DAX Snippet Reference" in text

    def test_export_json_to_file(self, manager: DAXManager, tmp_path: Path) -> None:
        output = tmp_path / "export" / "snippets.json"
        manager.export(fmt="json", output_path=output)
        data = json.loads(output.read_text(encoding="utf-8"))
        assert len(data) == 10


# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------

class TestValidate:
    """Tests for the 'validate' subcommand."""

    def test_default_snippets_pass(self, manager: DAXManager) -> None:
        """All default snippets should use DIVIDE and VAR/RETURN."""
        issues = manager.validate()
        # Default snippets are clean — no high-severity issues expected
        high = [i for i in issues if i["severity"] == "high"]
        assert high == []

    def test_catches_raw_division(self, empty_manager: DAXManager) -> None:
        empty_manager.add(
            name="Bad Division",
            dax="Bad Ratio = [Sales] / [Cost]",
        )
        issues = empty_manager.validate()
        assert any("raw division" in i["issue"].lower() for i in issues)

    def test_catches_format(self, empty_manager: DAXManager) -> None:
        empty_manager.add(
            name="Bad Format",
            dax='VAR _x = FORMAT([Sales], "#,##0")\nRETURN _x',
        )
        issues = empty_manager.validate()
        assert any("FORMAT()" in i["issue"] for i in issues)

    def test_catches_missing_var_return(self, empty_manager: DAXManager) -> None:
        empty_manager.add(
            name="No VAR",
            dax="Simple = SUM(Sales[Amount])",
        )
        issues = empty_manager.validate()
        assert any("VAR/RETURN" in i["issue"] for i in issues)

    def test_validate_empty_db(self, empty_manager: DAXManager) -> None:
        issues = empty_manager.validate()
        assert issues == []


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge case tests."""

    def test_unicode_in_dax(self, manager: DAXManager) -> None:
        """DAX with Unicode comments should be handled correctly."""
        snippet = manager.add(
            name="Unicode Test",
            dax="-- Тестова міра (українська)\nVAR _x = 1\nRETURN _x",
            tags=["unicode", "test"],
        )
        assert snippet["id"] == "unicode-test"
        # Verify it persists and reloads
        reloaded = DAXManager(storage_path=manager.storage_path)
        found = reloaded.search("українська")
        assert len(found) == 1

    def test_multiline_dax(self, manager: DAXManager) -> None:
        dax = "VAR _a = 1\nVAR _b = 2\nVAR _c = _a + _b\nRETURN _c"
        snippet = manager.add(name="Multiline", dax=dax)
        assert snippet["dax"] == dax

    def test_search_after_add(self, manager: DAXManager) -> None:
        """Newly added snippet should be immediately searchable."""
        manager.add(
            name="Zebra Metric",
            dax="VAR _z = 42\nRETURN _z",
            tags=["zebra"],
        )
        results = manager.search("zebra")
        assert len(results) == 1
        assert results[0]["name"] == "Zebra Metric"
