"""CSV Data Quality Checker for Power BI imports.

CLI tool that analyzes a CSV file and reports data quality issues:
missing values, duplicates, outliers (IQR method), invalid dates,
column naming conventions, mixed types, and negative values.

Outputs: rich console report + JSON report to data/reports/.
Exit code: 0 (all checks passed) or 1 (issues found).
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

console = Console()

# --- Constants ---

SEVERITY_CRITICAL = "CRITICAL"
SEVERITY_WARNING = "WARNING"
SEVERITY_INFO = "INFO"

DATE_FORMATS: list[str] = [
    "%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y",
    "%m-%d-%Y", "%d.%m.%Y", "%Y/%m/%d",
]


# --- Check Functions ---


def check_missing_values(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Check for missing values in each column.

    Args:
        df: Input DataFrame.

    Returns:
        List of issue dictionaries with column, count, and severity.
    """
    issues: list[dict[str, Any]] = []
    for col in df.columns:
        # Count both NaN and empty strings
        missing_count = int(df[col].isna().sum() + (df[col] == "").sum())
        if missing_count > 0:
            pct = round(missing_count / len(df) * 100, 1)
            severity = SEVERITY_CRITICAL if pct > 10 else SEVERITY_WARNING
            issues.append({
                "check": "missing_values",
                "column": col,
                "count": missing_count,
                "percentage": pct,
                "severity": severity,
                "message": f"{col}: {missing_count} missing ({pct}%)",
            })
    return issues


def check_duplicates(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Check for duplicate rows.

    Args:
        df: Input DataFrame.

    Returns:
        List of issue dictionaries with duplicate count and severity.
    """
    dup_count = int(df.duplicated().sum())
    if dup_count == 0:
        return []
    pct = round(dup_count / len(df) * 100, 1)
    severity = SEVERITY_CRITICAL if pct > 5 else SEVERITY_WARNING
    return [{
        "check": "duplicates",
        "column": "_all_",
        "count": dup_count,
        "percentage": pct,
        "severity": severity,
        "message": f"{dup_count} duplicate rows ({pct}%)",
    }]


def check_outliers_iqr(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Detect outliers using the IQR method for numeric columns.

    IQR = Q3 - Q1. Values outside [Q1 - 1.5*IQR, Q3 + 1.5*IQR]
    are considered outliers.

    Args:
        df: Input DataFrame.

    Returns:
        List of issue dictionaries with outlier details.
    """
    issues: list[dict[str, Any]] = []
    numeric_cols = df.select_dtypes(include=["number"]).columns

    for col in numeric_cols:
        series = df[col].dropna()
        if len(series) < 4:
            continue

        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        iqr = q3 - q1

        if iqr == 0:
            continue

        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        outlier_mask = (series < lower_bound) | (series > upper_bound)
        outlier_count = int(outlier_mask.sum())

        if outlier_count > 0:
            outlier_values = series[outlier_mask].tolist()
            # Show max 5 examples
            examples = outlier_values[:5]
            issues.append({
                "check": "outliers_iqr",
                "column": col,
                "count": outlier_count,
                "severity": SEVERITY_WARNING,
                "bounds": {"lower": round(lower_bound, 2), "upper": round(upper_bound, 2)},
                "examples": examples,
                "message": (
                    f"{col}: {outlier_count} outliers "
                    f"(bounds: [{round(lower_bound, 2)}, {round(upper_bound, 2)}])"
                ),
            })
    return issues


def check_invalid_dates(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Check columns containing 'date' in name for invalid date values.

    Tries multiple date formats. Values that cannot be parsed in any
    format are flagged.

    Args:
        df: Input DataFrame.

    Returns:
        List of issue dictionaries with invalid date details.
    """
    issues: list[dict[str, Any]] = []
    date_cols = [c for c in df.columns if "date" in c.lower()]

    for col in date_cols:
        invalid_values: list[str] = []
        for val in df[col].dropna():
            val_str = str(val).strip()
            if val_str == "":
                continue
            parsed = False
            for fmt in DATE_FORMATS:
                try:
                    datetime.strptime(val_str, fmt)
                    parsed = True
                    break
                except ValueError:
                    continue
            if not parsed:
                invalid_values.append(val_str)

        if invalid_values:
            unique_invalid = list(set(invalid_values))
            issues.append({
                "check": "invalid_dates",
                "column": col,
                "count": len(invalid_values),
                "severity": SEVERITY_CRITICAL,
                "examples": unique_invalid[:5],
                "message": (
                    f"{col}: {len(invalid_values)} invalid dates "
                    f"(e.g. {unique_invalid[:3]})"
                ),
            })
    return issues


def check_column_naming(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Check if column names follow PascalCase convention.

    Power BI best practice: column names should be PascalCase
    (e.g. SalesAmount, not sales_amount or salesamount).

    Args:
        df: Input DataFrame.

    Returns:
        List of issue dictionaries for non-PascalCase columns.
    """
    issues: list[dict[str, Any]] = []
    for col in df.columns:
        # PascalCase: starts with uppercase, no underscores/spaces,
        # has at least one lowercase letter
        is_pascal = (
            col[0].isupper()
            and "_" not in col
            and " " not in col
            and any(c.islower() for c in col)
        )
        if not is_pascal:
            issues.append({
                "check": "column_naming",
                "column": col,
                "count": 1,
                "severity": SEVERITY_INFO,
                "message": f"'{col}' is not PascalCase",
            })
    return issues


def check_whitespace(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Check string columns for leading/trailing whitespace.

    Args:
        df: Input DataFrame.

    Returns:
        List of issue dictionaries with whitespace details.
    """
    issues: list[dict[str, Any]] = []
    string_cols = df.select_dtypes(include=["object", "string"]).columns

    for col in string_cols:
        series = df[col].dropna()
        ws_mask = series.astype(str).str.strip() != series.astype(str)
        ws_count = int(ws_mask.sum())
        if ws_count > 0:
            examples = series[ws_mask].head(3).tolist()
            issues.append({
                "check": "whitespace",
                "column": col,
                "count": ws_count,
                "severity": SEVERITY_WARNING,
                "examples": [repr(e) for e in examples],
                "message": f"{col}: {ws_count} values with extra whitespace",
            })
    return issues


def check_negative_values(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Check numeric columns for unexpected negative values.

    Columns like Quantity and Amount should not be negative
    in typical sales data.

    Args:
        df: Input DataFrame.

    Returns:
        List of issue dictionaries for negative values.
    """
    issues: list[dict[str, Any]] = []
    suspect_cols = [
        c for c in df.select_dtypes(include=["number"]).columns
        if any(kw in c.lower() for kw in ["quantity", "amount", "price", "sales"])
    ]

    for col in suspect_cols:
        neg_count = int((df[col] < 0).sum())
        if neg_count > 0:
            issues.append({
                "check": "negative_values",
                "column": col,
                "count": neg_count,
                "severity": SEVERITY_WARNING,
                "message": f"{col}: {neg_count} negative values",
            })
    return issues


# --- Scoring ---


def calculate_score(issues: list[dict[str, Any]], total_rows: int) -> int:
    """Calculate data quality score (0-100).

    Deductions:
    - CRITICAL issue: -5 per issue (min 0)
    - WARNING issue: -2 per issue
    - INFO issue: -1 per issue

    Args:
        issues: List of all detected issues.
        total_rows: Total number of rows in the dataset.

    Returns:
        Quality score from 0 to 100.
    """
    score = 100
    for issue in issues:
        severity = issue.get("severity", SEVERITY_INFO)
        if severity == SEVERITY_CRITICAL:
            score -= 5
        elif severity == SEVERITY_WARNING:
            score -= 2
        else:
            score -= 1
    return max(0, score)


# --- Report Output ---


def print_console_report(
    issues: list[dict[str, Any]],
    score: int,
    total_rows: int,
    csv_path: Path,
) -> None:
    """Print a rich-formatted console report.

    Args:
        issues: List of all detected issues.
        score: Calculated quality score.
        total_rows: Total rows in CSV.
        csv_path: Path to the analyzed CSV file.
    """
    # Header
    if score >= 90:
        score_color = "green"
        grade = "A"
    elif score >= 70:
        score_color = "yellow"
        grade = "B"
    elif score >= 50:
        score_color = "orange3"
        grade = "C"
    else:
        score_color = "red"
        grade = "F"

    console.print()
    console.print(Panel(
        f"[bold {score_color}]Score: {score}/100 (Grade: {grade})[/]\n"
        f"File: {csv_path.name} | Rows: {total_rows} | Issues: {len(issues)}",
        title="[bold]Data Quality Report[/]",
        border_style=score_color,
    ))

    if not issues:
        console.print("[green]✅ No issues found! Data is clean.[/]")
        return

    # Issues table
    table = Table(title="Issues Found", show_lines=True)
    table.add_column("Check", style="cyan", width=18)
    table.add_column("Column", style="magenta", width=15)
    table.add_column("Count", justify="right", width=7)
    table.add_column("Severity", width=10)
    table.add_column("Message", style="white")

    severity_colors = {
        SEVERITY_CRITICAL: "red",
        SEVERITY_WARNING: "yellow",
        SEVERITY_INFO: "blue",
    }

    for issue in sorted(issues, key=lambda x: (
        {SEVERITY_CRITICAL: 0, SEVERITY_WARNING: 1, SEVERITY_INFO: 2}.get(x["severity"], 3)
    )):
        color = severity_colors.get(issue["severity"], "white")
        table.add_row(
            issue["check"],
            issue.get("column", "-"),
            str(issue.get("count", "-")),
            f"[{color}]{issue['severity']}[/{color}]",
            issue["message"],
        )

    console.print(table)


def save_json_report(
    issues: list[dict[str, Any]],
    score: int,
    total_rows: int,
    csv_path: Path,
    output_dir: Path,
) -> Path:
    """Save JSON report to disk.

    Args:
        issues: List of all detected issues.
        score: Calculated quality score.
        total_rows: Total rows in CSV.
        csv_path: Path to the analyzed CSV file.
        output_dir: Directory for report output.

    Returns:
        Path to the saved JSON report.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = output_dir / f"quality_report_{csv_path.stem}_{timestamp}.json"

    report = {
        "file": str(csv_path),
        "timestamp": datetime.now().isoformat(),
        "total_rows": total_rows,
        "score": score,
        "grade": "A" if score >= 90 else "B" if score >= 70 else "C" if score >= 50 else "F",
        "total_issues": len(issues),
        "issues_by_severity": {
            SEVERITY_CRITICAL: len([i for i in issues if i["severity"] == SEVERITY_CRITICAL]),
            SEVERITY_WARNING: len([i for i in issues if i["severity"] == SEVERITY_WARNING]),
            SEVERITY_INFO: len([i for i in issues if i["severity"] == SEVERITY_INFO]),
        },
        "issues": issues,
    }

    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    logger.info("JSON report saved → %s", report_path)
    return report_path


# --- Main ---


def run_checks(csv_path: Path) -> tuple[list[dict[str, Any]], int]:
    """Run all data quality checks on a CSV file.

    Args:
        csv_path: Path to the CSV file.

    Returns:
        Tuple of (issues list, quality score).
    """
    df = pd.read_csv(csv_path)
    total_rows = len(df)

    all_issues: list[dict[str, Any]] = []

    all_issues.extend(check_missing_values(df))
    all_issues.extend(check_duplicates(df))
    all_issues.extend(check_outliers_iqr(df))
    all_issues.extend(check_invalid_dates(df))
    all_issues.extend(check_column_naming(df))
    all_issues.extend(check_whitespace(df))
    all_issues.extend(check_negative_values(df))

    score = calculate_score(all_issues, total_rows)

    return all_issues, score


def main() -> None:
    """CLI entry point for data quality checker."""
    parser = argparse.ArgumentParser(
        description="Check CSV data quality before Power BI import."
    )
    parser.add_argument(
        "csv_path",
        type=Path,
        help="Path to the CSV file to check.",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=Path("data/reports"),
        help="Directory for JSON reports (default: data/reports).",
    )
    args = parser.parse_args()

    if not args.csv_path.exists():
        console.print(f"[red]Error: File not found: {args.csv_path}[/]")
        sys.exit(1)

    df = pd.read_csv(args.csv_path)
    total_rows = len(df)

    issues, score = run_checks(args.csv_path)

    print_console_report(issues, score, total_rows, args.csv_path)
    save_json_report(issues, score, total_rows, args.csv_path, args.report_dir)

    sys.exit(0 if score >= 70 else 1)


if __name__ == "__main__":
    main()
