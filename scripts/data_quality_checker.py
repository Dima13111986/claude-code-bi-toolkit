"""CSV Data Quality Checker for Power BI data preparation.

Analyzes CSV files for common quality issues: missing values, duplicates,
outliers (IQR method), invalid dates, whitespace, negative values,
and column naming. Supports auto-fix mode and HTML report generation.

Exit codes: 0 = quality score >= 70, 1 = score < 70 (CI/CD compatible).
"""

import argparse
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Analysis helpers
# ---------------------------------------------------------------------------

def check_missing_values(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Detect columns with missing (NaN/None) values.

    Args:
        df: Input DataFrame.

    Returns:
        List of issue dicts with column, count, and percentage.
    """
    issues: list[dict[str, Any]] = []
    for col in df.columns:
        missing = int(df[col].isna().sum())
        if missing > 0:
            pct = round(missing / len(df) * 100, 1)
            issues.append({
                "type": "missing_value",
                "column": col,
                "count": missing,
                "percentage": pct,
                "severity": "high" if pct > 10 else "medium" if pct > 5 else "low",
            })
    return issues


def check_duplicates(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Detect exact duplicate rows.

    Args:
        df: Input DataFrame.

    Returns:
        List with one issue dict if duplicates found.
    """
    dupes = int(df.duplicated().sum())
    if dupes > 0:
        pct = round(dupes / len(df) * 100, 1)
        return [{
            "type": "duplicate_rows",
            "count": dupes,
            "percentage": pct,
            "severity": "high" if pct > 5 else "medium",
        }]
    return []


def check_outliers_iqr(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Detect outliers using the IQR method on numeric columns.

    IQR = Q3 - Q1. Values below Q1 - 1.5*IQR or above Q3 + 1.5*IQR
    are flagged as outliers.

    Args:
        df: Input DataFrame.

    Returns:
        List of issue dicts per column with outlier details.
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
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        outlier_mask = (series < lower) | (series > upper)
        count = int(outlier_mask.sum())
        if count > 0:
            issues.append({
                "type": "outlier",
                "column": col,
                "count": count,
                "bounds": {"lower": round(lower, 2), "upper": round(upper, 2)},
                "severity": "medium",
            })
    return issues


def check_invalid_dates(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Detect values in date-like columns that cannot be parsed.

    Columns with 'date' in the name (case-insensitive) are checked.

    Args:
        df: Input DataFrame.

    Returns:
        List of issue dicts with invalid date details.
    """
    issues: list[dict[str, Any]] = []
    date_cols = [c for c in df.columns if "date" in c.lower()]
    for col in date_cols:
        series = df[col].dropna().astype(str)
        parsed = pd.to_datetime(series, errors="coerce", format="mixed")
        invalid_count = int(parsed.isna().sum())
        if invalid_count > 0:
            samples = series[parsed.isna()].head(3).tolist()
            issues.append({
                "type": "invalid_date",
                "column": col,
                "count": invalid_count,
                "samples": samples,
                "severity": "high",
            })
    return issues


def check_whitespace(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Detect leading/trailing whitespace in string columns.

    Args:
        df: Input DataFrame.

    Returns:
        List of issue dicts per column with whitespace problems.
    """
    issues: list[dict[str, Any]] = []
    str_cols = df.select_dtypes(include=["object", "string"]).columns
    for col in str_cols:
        series = df[col].dropna().astype(str)
        ws_mask = series != series.str.strip()
        count = int(ws_mask.sum())
        if count > 0:
            issues.append({
                "type": "whitespace",
                "column": col,
                "count": count,
                "severity": "low",
            })
    return issues


def check_negative_values(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Detect negative values in numeric columns where they are unexpected.

    Columns with 'amount', 'quantity', 'price', 'count' in name are checked.

    Args:
        df: Input DataFrame.

    Returns:
        List of issue dicts per column with negative value counts.
    """
    issues: list[dict[str, Any]] = []
    keywords = ["amount", "quantity", "price", "count"]
    for col in df.select_dtypes(include=["number"]).columns:
        if any(kw in col.lower() for kw in keywords):
            neg_count = int((df[col].dropna() < 0).sum())
            if neg_count > 0:
                issues.append({
                    "type": "negative_value",
                    "column": col,
                    "count": neg_count,
                    "severity": "high",
                })
    return issues


def check_column_naming(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Check if column names follow PascalCase convention.

    Args:
        df: Input DataFrame.

    Returns:
        List of issue dicts for non-PascalCase column names.
    """
    issues: list[dict[str, Any]] = []
    pascal_re = re.compile(r"^[A-Z][a-zA-Z0-9]*$")
    for col in df.columns:
        if not pascal_re.match(col):
            issues.append({
                "type": "naming_convention",
                "column": col,
                "expected": "PascalCase",
                "severity": "low",
            })
    return issues


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

SEVERITY_WEIGHTS = {"high": 10, "medium": 5, "low": 2}


def calculate_score(issues: list[dict[str, Any]], row_count: int) -> int:
    """Calculate a quality score from 0 to 100.

    Each issue deducts points based on severity. The score cannot go
    below 0.

    Args:
        issues: Collected issues from all checks.
        row_count: Total rows in the DataFrame.

    Returns:
        Integer score 0–100.
    """
    if row_count == 0:
        return 100
    penalty = sum(SEVERITY_WEIGHTS.get(i.get("severity", "low"), 2) for i in issues)
    score = max(0, 100 - penalty)
    return score


def score_to_grade(score: int) -> str:
    """Convert numeric score to letter grade.

    Args:
        score: Quality score 0–100.

    Returns:
        Letter grade: A, B, C, D, or F.
    """
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


# ---------------------------------------------------------------------------
# Fix mode
# ---------------------------------------------------------------------------

def apply_fixes(df: pd.DataFrame, issues: list[dict[str, Any]]) -> pd.DataFrame:
    """Auto-correct common data quality issues.

    Creates a COPY of the DataFrame. Never modifies the original.
    Fixes applied:
      - Strip whitespace from string columns
      - Rename columns to PascalCase
      - Remove exact duplicate rows

    Args:
        df: Original DataFrame (not modified).
        issues: Issues list from analysis (used for context).

    Returns:
        New DataFrame with fixes applied.
    """
    fixed = df.copy()

    # 1. Strip whitespace from all string columns
    for col in fixed.select_dtypes(include=["object", "string"]).columns:
        fixed[col] = fixed[col].astype(str).str.strip()
        # Restore actual NaN where we converted None → "None"
        fixed[col] = fixed[col].replace("None", pd.NA)
        fixed[col] = fixed[col].replace("nan", pd.NA)

    # 2. PascalCase column names
    def to_pascal_case(name: str) -> str:
        """Convert a column name to PascalCase.

        Args:
            name: Original column name.

        Returns:
            PascalCase version of the name.
        """
        parts = re.split(r"[_\-\s]+", name)
        return "".join(part.capitalize() for part in parts if part)

    fixed.columns = [to_pascal_case(c) for c in fixed.columns]

    # 3. Remove exact duplicates
    before = len(fixed)
    fixed = fixed.drop_duplicates().reset_index(drop=True)
    removed = before - len(fixed)
    if removed > 0:
        logger.info("Removed %d duplicate rows", removed)

    return fixed


# ---------------------------------------------------------------------------
# Reports — Console (rich)
# ---------------------------------------------------------------------------

def print_console_report(
    issues: list[dict[str, Any]],
    score: int,
    grade: str,
    csv_path: Path,
) -> None:
    """Print a formatted quality report to the console using rich.

    Args:
        issues: All detected issues.
        score: Calculated quality score.
        grade: Letter grade.
        csv_path: Path to the analyzed CSV file.
    """
    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:
        # Fallback to plain print if rich is not installed
        print(f"\n=== Data Quality Report: {csv_path.name} ===")
        print(f"Score: {score}/100 (Grade: {grade})")
        print(f"Issues found: {len(issues)}")
        for issue in issues:
            print(f"  - [{issue.get('severity', '?')}] {issue.get('type', '?')}: "
                  f"{issue.get('column', 'N/A')} ({issue.get('count', 0)})")
        return

    console = Console()
    console.print(f"\n[bold]Data Quality Report:[/bold] {csv_path.name}")
    console.print(f"Score: [bold]{score}[/bold]/100  Grade: [bold]{grade}[/bold]\n")

    if not issues:
        console.print("[green]No issues found! Perfect quality.[/green]")
        return

    table = Table(title=f"{len(issues)} Issues Found")
    table.add_column("Type", style="cyan")
    table.add_column("Column", style="white")
    table.add_column("Count", justify="right")
    table.add_column("Severity", style="bold")

    severity_colors = {"high": "red", "medium": "yellow", "low": "green"}
    for issue in sorted(issues, key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x.get("severity", "low"), 3)):
        sev = issue.get("severity", "low")
        color = severity_colors.get(sev, "white")
        table.add_row(
            issue.get("type", ""),
            issue.get("column", "—"),
            str(issue.get("count", "")),
            f"[{color}]{sev.upper()}[/{color}]",
        )

    console.print(table)


# ---------------------------------------------------------------------------
# Reports — JSON
# ---------------------------------------------------------------------------

def save_json_report(
    issues: list[dict[str, Any]],
    score: int,
    grade: str,
    csv_path: Path,
    output_dir: Path,
) -> Path:
    """Save quality report as JSON.

    Args:
        issues: All detected issues.
        score: Quality score.
        grade: Letter grade.
        csv_path: Analyzed CSV path.
        output_dir: Directory for the JSON report.

    Returns:
        Path to the saved JSON report.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = output_dir / f"quality_report_{csv_path.stem}_{timestamp}.json"

    report = {
        "file": str(csv_path),
        "timestamp": datetime.now().isoformat(),
        "score": score,
        "grade": grade,
        "issues_count": len(issues),
        "issues": issues,
    }

    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    logger.info("JSON report saved → %s", report_path)
    return report_path


# ---------------------------------------------------------------------------
# Reports — HTML
# ---------------------------------------------------------------------------

def generate_html_report(
    issues: list[dict[str, Any]],
    score: int,
    grade: str,
    csv_path: Path,
    output_dir: Path,
) -> Path:
    """Generate a self-contained HTML report with inline CSS and SVG charts.

    Features:
      - Score gauge (SVG arc)
      - Color-coded issue table
      - Issue distribution bar chart (SVG)
      - Fully inline CSS — no external dependencies

    Args:
        issues: All detected issues.
        score: Quality score.
        grade: Letter grade.
        csv_path: Analyzed CSV path.
        output_dir: Directory for the HTML report.

    Returns:
        Path to the saved HTML report.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = output_dir / f"quality_report_{csv_path.stem}_{timestamp}.html"

    # --- Score color ---
    if score >= 90:
        score_color = "#22c55e"  # green
    elif score >= 70:
        score_color = "#f59e0b"  # amber
    else:
        score_color = "#ef4444"  # red

    # --- SVG gauge ---
    angle = score / 100 * 180  # half-circle gauge
    rad = angle * 3.14159 / 180
    # Arc endpoint
    cx, cy, r = 100, 100, 80
    import math
    end_x = cx - r * math.cos(rad)
    end_y = cy - r * math.sin(rad)
    large_arc = 1 if angle > 90 else 0

    gauge_svg = f"""
    <svg width="220" height="130" viewBox="0 0 220 130">
      <path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="#e5e7eb" stroke-width="16" stroke-linecap="round"/>
      <path d="M 20 100 A 80 80 0 {large_arc} 1 {end_x:.1f} {end_y:.1f}" fill="none" stroke="{score_color}" stroke-width="16" stroke-linecap="round"/>
      <text x="100" y="95" text-anchor="middle" font-size="32" font-weight="bold" fill="{score_color}">{score}</text>
      <text x="100" y="118" text-anchor="middle" font-size="14" fill="#6b7280">Grade: {grade}</text>
    </svg>
    """

    # --- Issue distribution bar chart (SVG) ---
    type_counts: dict[str, int] = {}
    for issue in issues:
        t = issue.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    bar_height = 28
    bar_gap = 6
    chart_height = len(type_counts) * (bar_height + bar_gap) + 10
    max_count = max(type_counts.values()) if type_counts else 1
    bar_max_width = 300

    bars_svg_parts: list[str] = []
    for i, (t, cnt) in enumerate(sorted(type_counts.items(), key=lambda x: -x[1])):
        y = i * (bar_height + bar_gap) + 5
        w = max(cnt / max_count * bar_max_width, 20)
        label = t.replace("_", " ").title()
        bars_svg_parts.append(
            f'<rect x="150" y="{y}" width="{w:.0f}" height="{bar_height}" rx="4" fill="{score_color}" opacity="0.8"/>'
            f'<text x="145" y="{y + 19}" text-anchor="end" font-size="13" fill="#374151">{label}</text>'
            f'<text x="{150 + w + 8:.0f}" y="{y + 19}" font-size="13" fill="#374151">{cnt}</text>'
        )
    bars_svg = f'<svg width="520" height="{chart_height}">{"".join(bars_svg_parts)}</svg>'

    # --- Issue table rows ---
    severity_colors_html = {"high": "#fee2e2", "medium": "#fef3c7", "low": "#d1fae5"}
    severity_text_colors = {"high": "#b91c1c", "medium": "#92400e", "low": "#065f46"}
    table_rows: list[str] = []
    for issue in sorted(issues, key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x.get("severity", "low"), 3)):
        sev = issue.get("severity", "low")
        bg = severity_colors_html.get(sev, "#f3f4f6")
        tc = severity_text_colors.get(sev, "#111")
        table_rows.append(
            f'<tr>'
            f'<td>{issue.get("type", "").replace("_", " ").title()}</td>'
            f'<td>{issue.get("column", "—")}</td>'
            f'<td style="text-align:right">{issue.get("count", "")}</td>'
            f'<td style="background:{bg};color:{tc};font-weight:600;text-align:center;border-radius:4px">{sev.upper()}</td>'
            f'</tr>'
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Data Quality Report — {csv_path.name}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: #f9fafb; color: #111827; padding: 2rem; }}
  .container {{ max-width: 800px; margin: 0 auto; }}
  .header {{ text-align: center; margin-bottom: 2rem; }}
  .header h1 {{ font-size: 1.5rem; color: #111827; }}
  .header p {{ color: #6b7280; font-size: 0.9rem; }}
  .card {{ background: #fff; border-radius: 12px; padding: 1.5rem;
           margin-bottom: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,.1); }}
  .card h2 {{ font-size: 1.1rem; margin-bottom: 1rem; color: #374151; }}
  .gauge-center {{ display: flex; justify-content: center; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ padding: 0.6rem 0.8rem; text-align: left; border-bottom: 1px solid #e5e7eb; font-size: 0.9rem; }}
  th {{ background: #f9fafb; font-weight: 600; color: #374151; }}
  .footer {{ text-align: center; color: #9ca3af; font-size: 0.8rem; margin-top: 2rem; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>Data Quality Report</h1>
    <p>{csv_path.name} &mdash; {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
  </div>

  <div class="card">
    <h2>Quality Score</h2>
    <div class="gauge-center">{gauge_svg}</div>
  </div>

  <div class="card">
    <h2>Issue Distribution</h2>
    {bars_svg if type_counts else '<p style="color:#6b7280">No issues found.</p>'}
  </div>

  <div class="card">
    <h2>Issues Detail ({len(issues)} total)</h2>
    {"<table><thead><tr><th>Type</th><th>Column</th><th>Count</th><th>Severity</th></tr></thead><tbody>" + "".join(table_rows) + "</tbody></table>" if table_rows else '<p style="color:#22c55e;font-weight:600">Perfect quality — no issues detected!</p>'}
  </div>

  <div class="footer">Generated by BI Toolkit &mdash; Data Quality Checker</div>
</div>
</body>
</html>"""

    report_path.write_text(html, encoding="utf-8")
    logger.info("HTML report saved → %s", report_path)
    return report_path


# ---------------------------------------------------------------------------
# Main analysis pipeline
# ---------------------------------------------------------------------------

def analyze_csv(csv_path: Path) -> tuple[pd.DataFrame, list[dict[str, Any]], int, str]:
    """Run all quality checks on a CSV file.

    Args:
        csv_path: Path to the CSV file.

    Returns:
        Tuple of (DataFrame, issues list, score, grade).
    """
    df = pd.read_csv(csv_path)
    logger.info("Loaded %d rows, %d columns from %s", len(df), len(df.columns), csv_path.name)

    issues: list[dict[str, Any]] = []
    issues.extend(check_missing_values(df))
    issues.extend(check_duplicates(df))
    issues.extend(check_outliers_iqr(df))
    issues.extend(check_invalid_dates(df))
    issues.extend(check_whitespace(df))
    issues.extend(check_negative_values(df))
    issues.extend(check_column_naming(df))

    score = calculate_score(issues, len(df))
    grade = score_to_grade(score)

    return df, issues, score, grade


def main() -> None:
    """CLI entry point for data quality checker."""
    parser = argparse.ArgumentParser(
        description="CSV Data Quality Checker for Power BI preparation."
    )
    parser.add_argument(
        "csv_path",
        type=Path,
        help="Path to the CSV file to analyze.",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=Path("data/reports"),
        help="Directory for reports (default: data/reports).",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Auto-fix issues and save as <name>_clean.csv.",
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Generate HTML report with SVG charts.",
    )

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if not args.csv_path.exists():
        logger.error("File not found: %s", args.csv_path)
        sys.exit(1)

    df, issues, score, grade = analyze_csv(args.csv_path)

    # Console report
    print_console_report(issues, score, grade, args.csv_path)

    # JSON report (always)
    save_json_report(issues, score, grade, args.csv_path, args.report_dir)

    # HTML report (optional)
    if args.html:
        generate_html_report(issues, score, grade, args.csv_path, args.report_dir)

    # Fix mode (optional)
    if args.fix:
        fixed_df = apply_fixes(df, issues)
        clean_path = args.csv_path.parent / f"{args.csv_path.stem}_clean.csv"
        fixed_df.to_csv(clean_path, index=False)
        logger.info("Fixed CSV saved → %s", clean_path)

        # Re-analyze the fixed file
        _, fixed_issues, fixed_score, fixed_grade = analyze_csv(clean_path)
        logger.info(
            "After fix: score %d → %d (grade %s → %s), issues %d → %d",
            score, fixed_score, grade, fixed_grade, len(issues), len(fixed_issues),
        )

    # Exit code for CI/CD
    sys.exit(0 if score >= 70 else 1)


if __name__ == "__main__":
    main()
