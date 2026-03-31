"""Tests for data_quality_checker.py — CSV Data Quality Checker.

Covers: clean CSV (score=100), missing values, duplicates, --fix mode,
empty CSV, single row, PascalCase detection, outliers, HTML report.

Fixtures stored in data/test_fixtures/.
"""

import json
from pathlib import Path

import pandas as pd
import pytest

# We import functions directly from the module.
# In the real project this would be: from scripts.data_quality_checker import ...
# Here we use sys.path manipulation for standalone testing.
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from data_quality_checker import (
    analyze_csv,
    apply_fixes,
    calculate_score,
    check_column_naming,
    check_duplicates,
    check_invalid_dates,
    check_missing_values,
    check_negative_values,
    check_outliers_iqr,
    check_whitespace,
    generate_html_report,
    save_json_report,
    score_to_grade,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "data" / "test_fixtures"


@pytest.fixture
def clean_csv_path() -> Path:
    """Path to a perfectly clean CSV (expect score=100)."""
    return FIXTURES_DIR / "clean.csv"


@pytest.fixture
def missing_values_csv_path() -> Path:
    """Path to a CSV with missing values in every column."""
    return FIXTURES_DIR / "missing_values.csv"


@pytest.fixture
def duplicates_csv_path() -> Path:
    """Path to a CSV with exact duplicate rows."""
    return FIXTURES_DIR / "duplicates.csv"


@pytest.fixture
def single_row_csv_path() -> Path:
    """Path to a CSV with just one data row."""
    return FIXTURES_DIR / "single_row.csv"


@pytest.fixture
def empty_csv_path() -> Path:
    """Path to a CSV with headers only (zero data rows)."""
    return FIXTURES_DIR / "empty.csv"


@pytest.fixture
def clean_df(clean_csv_path: Path) -> pd.DataFrame:
    """Loaded clean DataFrame."""
    return pd.read_csv(clean_csv_path)


@pytest.fixture
def missing_df(missing_values_csv_path: Path) -> pd.DataFrame:
    """Loaded DataFrame with missing values."""
    return pd.read_csv(missing_values_csv_path)


@pytest.fixture
def duplicates_df(duplicates_csv_path: Path) -> pd.DataFrame:
    """Loaded DataFrame with duplicate rows."""
    return pd.read_csv(duplicates_csv_path)


@pytest.fixture
def tmp_report_dir(tmp_path: Path) -> Path:
    """Temporary directory for report output."""
    d = tmp_path / "reports"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# Test: Clean CSV → score 100, zero issues
# ---------------------------------------------------------------------------

class TestCleanCSV:
    """Clean CSV should produce a perfect score with no issues."""

    def test_score_is_100(self, clean_csv_path: Path) -> None:
        _, issues, score, grade = analyze_csv(clean_csv_path)
        assert score == 100
        assert grade == "A"
        assert len(issues) == 0

    def test_no_missing_values(self, clean_df: pd.DataFrame) -> None:
        assert check_missing_values(clean_df) == []

    def test_no_duplicates(self, clean_df: pd.DataFrame) -> None:
        assert check_duplicates(clean_df) == []

    def test_no_whitespace(self, clean_df: pd.DataFrame) -> None:
        assert check_whitespace(clean_df) == []


# ---------------------------------------------------------------------------
# Test: Missing values detection
# ---------------------------------------------------------------------------

class TestMissingValues:
    """CSV with missing values should be correctly detected."""

    def test_detects_missing(self, missing_df: pd.DataFrame) -> None:
        issues = check_missing_values(missing_df)
        assert len(issues) > 0
        columns_with_missing = {i["column"] for i in issues}
        # Our fixture has missing in OrderDate, Region, Product, SalesAmount, Quantity
        assert "SalesAmount" in columns_with_missing
        assert "OrderDate" in columns_with_missing

    def test_missing_count_correct(self, missing_df: pd.DataFrame) -> None:
        issues = check_missing_values(missing_df)
        for issue in issues:
            assert issue["count"] >= 1
            assert issue["percentage"] > 0

    def test_severity_assigned(self, missing_df: pd.DataFrame) -> None:
        issues = check_missing_values(missing_df)
        for issue in issues:
            assert issue["severity"] in ("low", "medium", "high")


# ---------------------------------------------------------------------------
# Test: Duplicates detection
# ---------------------------------------------------------------------------

class TestDuplicates:
    """CSV with duplicate rows should report them."""

    def test_detects_duplicates(self, duplicates_df: pd.DataFrame) -> None:
        issues = check_duplicates(duplicates_df)
        assert len(issues) == 1
        assert issues[0]["type"] == "duplicate_rows"
        assert issues[0]["count"] == 2  # 2 rows are dupes of existing ones

    def test_clean_has_no_duplicates(self, clean_df: pd.DataFrame) -> None:
        assert check_duplicates(clean_df) == []


# ---------------------------------------------------------------------------
# Test: --fix mode
# ---------------------------------------------------------------------------

class TestFixMode:
    """Auto-fix should strip whitespace, rename columns, remove dupes."""

    def test_fix_strips_whitespace(self) -> None:
        df = pd.DataFrame({"Region": [" North ", "South", " East"]})
        fixed = apply_fixes(df, [])
        assert list(fixed["Region"]) == ["North", "South", "East"]

    def test_fix_removes_duplicates(self) -> None:
        df = pd.DataFrame({
            "Name": ["Alice", "Alice", "Bob"],
            "Value": [1, 1, 2],
        })
        fixed = apply_fixes(df, [])
        assert len(fixed) == 2

    def test_fix_converts_to_pascal_case(self) -> None:
        df = pd.DataFrame({"order_date": ["01/01/2024"], "sales_amount": [100]})
        fixed = apply_fixes(df, [])
        assert "OrderDate" in fixed.columns
        assert "SalesAmount" in fixed.columns

    def test_fix_preserves_original(self) -> None:
        df = pd.DataFrame({"Name": [" Alice "]})
        original_copy = df.copy()
        _ = apply_fixes(df, [])
        pd.testing.assert_frame_equal(df, original_copy)

    def test_fix_creates_new_file(self, clean_csv_path: Path, tmp_path: Path) -> None:
        """--fix saves to <name>_clean.csv, never overwrites original."""
        import shutil
        test_csv = tmp_path / "test_data.csv"
        shutil.copy(clean_csv_path, test_csv)
        df = pd.read_csv(test_csv)
        fixed = apply_fixes(df, [])
        clean_path = tmp_path / "test_data_clean.csv"
        fixed.to_csv(clean_path, index=False)
        assert clean_path.exists()
        assert test_csv.exists()  # original untouched


# ---------------------------------------------------------------------------
# Test: Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Empty CSV, single row, and other edge cases."""

    def test_empty_csv_score_100(self, empty_csv_path: Path) -> None:
        _, issues, score, grade = analyze_csv(empty_csv_path)
        assert score == 100

    def test_single_row_no_crash(self, single_row_csv_path: Path) -> None:
        _, issues, score, grade = analyze_csv(single_row_csv_path)
        assert isinstance(score, int)
        assert grade in ("A", "B", "C", "D", "F")

    def test_calculate_score_empty_issues(self) -> None:
        assert calculate_score([], 100) == 100

    def test_calculate_score_zero_rows(self) -> None:
        assert calculate_score([], 0) == 100


# ---------------------------------------------------------------------------
# Test: PascalCase column naming
# ---------------------------------------------------------------------------

class TestColumnNaming:
    """Column naming convention checks."""

    def test_pascal_case_passes(self) -> None:
        df = pd.DataFrame({"OrderDate": [], "SalesAmount": []})
        assert check_column_naming(df) == []

    def test_snake_case_fails(self) -> None:
        df = pd.DataFrame({"order_date": [], "sales_amount": []})
        issues = check_column_naming(df)
        assert len(issues) == 2
        assert all(i["type"] == "naming_convention" for i in issues)

    def test_mixed_case_partial(self) -> None:
        df = pd.DataFrame({"OrderDate": [], "sales_amount": []})
        issues = check_column_naming(df)
        assert len(issues) == 1
        assert issues[0]["column"] == "sales_amount"


# ---------------------------------------------------------------------------
# Test: Outlier detection
# ---------------------------------------------------------------------------

class TestOutliers:
    """IQR-based outlier detection."""

    def test_detects_extreme_outlier(self) -> None:
        df = pd.DataFrame({"Amount": [100, 110, 105, 95, 108, 999999]})
        issues = check_outliers_iqr(df)
        assert len(issues) == 1
        assert issues[0]["count"] == 1

    def test_no_outliers_in_uniform_data(self) -> None:
        df = pd.DataFrame({"Amount": [100, 101, 102, 103, 104]})
        issues = check_outliers_iqr(df)
        assert len(issues) == 0

    def test_skips_small_series(self) -> None:
        """IQR needs at least 4 values to be meaningful."""
        df = pd.DataFrame({"Amount": [1, 2, 3]})
        assert check_outliers_iqr(df) == []


# ---------------------------------------------------------------------------
# Test: Score grading
# ---------------------------------------------------------------------------

class TestScoring:
    """Score-to-grade conversion."""

    @pytest.mark.parametrize("score,expected", [
        (100, "A"), (95, "A"), (90, "A"),
        (89, "B"), (80, "B"),
        (79, "C"), (70, "C"),
        (69, "D"), (60, "D"),
        (59, "F"), (0, "F"),
    ])
    def test_grade_boundaries(self, score: int, expected: str) -> None:
        assert score_to_grade(score) == expected


# ---------------------------------------------------------------------------
# Test: Reports
# ---------------------------------------------------------------------------

class TestReports:
    """JSON and HTML report generation."""

    def test_json_report_created(self, tmp_report_dir: Path) -> None:
        issues = [{"type": "test", "severity": "low", "count": 1}]
        path = save_json_report(issues, 95, "A", Path("test.csv"), tmp_report_dir)
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["score"] == 95
        assert data["grade"] == "A"
        assert len(data["issues"]) == 1

    def test_html_report_created(self, tmp_report_dir: Path) -> None:
        issues = [{"type": "missing_value", "column": "X", "count": 5, "severity": "high"}]
        path = generate_html_report(issues, 75, "C", Path("test.csv"), tmp_report_dir)
        assert path.exists()
        html = path.read_text()
        assert "Data Quality Report" in html
        assert "75" in html
        assert "<svg" in html  # SVG gauge present

    def test_html_report_inline_css(self, tmp_report_dir: Path) -> None:
        path = generate_html_report([], 100, "A", Path("test.csv"), tmp_report_dir)
        html = path.read_text()
        assert "<style>" in html
        assert '<link rel="stylesheet"' not in html  # no external CSS
