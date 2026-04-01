"""DAX Snippet Manager — CLI tool for storing, searching, and exporting DAX patterns.

Subcommands:
    add       Add a new DAX snippet
    search    Search snippets by keyword
    list      List all snippets (optional category filter)
    export    Export snippets to Markdown or JSON
    validate  Check snippets for DAX anti-patterns
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default storage path (relative to project root)
# ---------------------------------------------------------------------------
DEFAULT_STORAGE = Path("data/dax_snippets.json")


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _slugify(name: str) -> str:
    """Convert a display name to a URL-friendly slug.

    Examples:
        >>> _slugify("YTD Sales")
        'ytd-sales'
        >>> _slugify("% of Grand Total")
        'of-grand-total'
    """
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug


def _now_iso() -> str:
    """Return current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Default DAX snippets (from dax-patterns skill)
# ---------------------------------------------------------------------------

def _default_snippets() -> list[dict]:
    """Return 10 common DAX patterns pre-populated from dax-patterns skill."""
    ts = _now_iso()
    patterns = [
        {
            "name": "YTD Sales",
            "category": "time-intelligence",
            "description": "Year-to-Date sales with optional fiscal year support.",
            "dax": (
                "YTD Sales =\n"
                "VAR _Result =\n"
                "    CALCULATE(\n"
                "        [Total Sales],\n"
                '        DATESYTD(DimDate[Date], "6/30")\n'
                "    )\n"
                "RETURN\n"
                "    _Result"
            ),
            "tags": ["ytd", "time-intelligence", "fiscal"],
        },
        {
            "name": "Sales vs Previous Year",
            "category": "time-intelligence",
            "description": "Compare current sales to same period last year.",
            "dax": (
                "Sales vs PY =\n"
                "VAR _Current = [Total Sales]\n"
                "VAR _PY =\n"
                "    CALCULATE(\n"
                "        [Total Sales],\n"
                "        SAMEPERIODLASTYEAR(DimDate[Date])\n"
                "    )\n"
                "RETURN\n"
                "    DIVIDE(_Current - _PY, _PY, 0)"
            ),
            "tags": ["yoy", "time-intelligence", "comparison"],
        },
        {
            "name": "Running Total",
            "category": "cumulative",
            "description": "Cumulative running total over a date axis.",
            "dax": (
                "Running Total =\n"
                "VAR _MaxDate = MAX(DimDate[Date])\n"
                "VAR _Result =\n"
                "    CALCULATE(\n"
                "        [Total Sales],\n"
                "        DimDate[Date] <= _MaxDate,\n"
                "        ALL(DimDate[Date])\n"
                "    )\n"
                "RETURN\n"
                "    _Result"
            ),
            "tags": ["running-total", "cumulative"],
        },
        {
            "name": "Pct of Grand Total",
            "category": "ratio",
            "description": "Percentage contribution to the grand total.",
            "dax": (
                "% of Grand Total =\n"
                "VAR _Current = [Total Sales]\n"
                "VAR _GrandTotal =\n"
                "    CALCULATE(\n"
                "        [Total Sales],\n"
                "        ALL(DimProduct)\n"
                "    )\n"
                "RETURN\n"
                "    DIVIDE(_Current, _GrandTotal, 0)"
            ),
            "tags": ["percentage", "ratio", "grand-total"],
        },
        {
            "name": "Moving Average 3M",
            "category": "statistical",
            "description": "3-month moving average of sales.",
            "dax": (
                "Moving Avg 3M =\n"
                "VAR _Period = 3\n"
                "VAR _Result =\n"
                "    AVERAGEX(\n"
                "        DATESINPERIOD(\n"
                "            DimDate[Date],\n"
                "            MAX(DimDate[Date]),\n"
                "            -_Period,\n"
                "            MONTH\n"
                "        ),\n"
                "        [Total Sales]\n"
                "    )\n"
                "RETURN\n"
                "    _Result"
            ),
            "tags": ["moving-average", "statistical", "trend"],
        },
        {
            "name": "Cumulative Total",
            "category": "cumulative",
            "description": "Cumulative total within the current filter context.",
            "dax": (
                "Cumulative Total =\n"
                "VAR _CurrentDate = MAX(DimDate[Date])\n"
                "VAR _Result =\n"
                "    CALCULATE(\n"
                "        [Total Sales],\n"
                "        FILTER(\n"
                "            ALL(DimDate),\n"
                "            DimDate[Date] <= _CurrentDate\n"
                "        )\n"
                "    )\n"
                "RETURN\n"
                "    _Result"
            ),
            "tags": ["cumulative", "running"],
        },
        {
            "name": "Rank by Sales",
            "category": "ranking",
            "description": "Rank products or categories by total sales.",
            "dax": (
                "Rank by Sales =\n"
                "VAR _CurrentSales = [Total Sales]\n"
                "VAR _Result =\n"
                "    COUNTROWS(\n"
                "        FILTER(\n"
                "            ALL(DimProduct[ProductName]),\n"
                "            [Total Sales] > _CurrentSales\n"
                "        )\n"
                "    ) + 1\n"
                "RETURN\n"
                "    _Result"
            ),
            "tags": ["rank", "ranking", "top-n"],
        },
        {
            "name": "Distinct Customer Count",
            "category": "aggregation",
            "description": "Count of unique customers with transactions.",
            "dax": (
                "Distinct Customers =\n"
                "VAR _Result =\n"
                "    DISTINCTCOUNT(FactSales[CustomerID])\n"
                "RETURN\n"
                "    _Result"
            ),
            "tags": ["distinct", "count", "customers"],
        },
        {
            "name": "Safe DIVIDE Wrapper",
            "category": "utility",
            "description": "Template for safe division — never use raw /.",
            "dax": (
                "Safe Ratio =\n"
                "VAR _Numerator = [Measure A]\n"
                "VAR _Denominator = [Measure B]\n"
                "RETURN\n"
                "    DIVIDE(_Numerator, _Denominator, 0)"
            ),
            "tags": ["divide", "safe", "utility", "template"],
        },
        {
            "name": "Dynamic Top N",
            "category": "ranking",
            "description": "Show top N items controlled by a slicer parameter.",
            "dax": (
                "Is Top N =\n"
                "VAR _N = SELECTEDVALUE(TopNParameter[Value], 10)\n"
                "VAR _Rank = [Rank by Sales]\n"
                "RETURN\n"
                "    IF(_Rank <= _N, 1, 0)"
            ),
            "tags": ["top-n", "dynamic", "slicer", "parameter"],
        },
    ]

    snippets = []
    for p in patterns:
        snippets.append(
            {
                "id": _slugify(p["name"]),
                "name": p["name"],
                "category": p["category"],
                "description": p["description"],
                "dax": p["dax"],
                "tags": p["tags"],
                "created": ts,
                "modified": ts,
            }
        )
    return snippets


# ---------------------------------------------------------------------------
# DAXManager class
# ---------------------------------------------------------------------------

class DAXManager:
    """Manages a collection of DAX snippets stored in a JSON file."""

    def __init__(self, storage_path: Path = DEFAULT_STORAGE) -> None:
        self.storage_path = storage_path
        self._ensure_storage()
        self._data = self._load()

    # -- Storage helpers ----------------------------------------------------

    def _ensure_storage(self) -> None:
        """Create storage file with default snippets if missing."""
        if not self.storage_path.exists():
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            default_data = {
                "version": "1.0.0",
                "snippets": _default_snippets(),
            }
            self._save_raw(default_data)
            logger.info("Created %s with %d default snippets", self.storage_path, 10)

    def _load(self) -> dict:
        """Load JSON storage from disk."""
        text = self.storage_path.read_text(encoding="utf-8")
        return json.loads(text)

    def _save_raw(self, data: dict) -> None:
        """Write raw data dict to storage file."""
        self.storage_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def _save(self) -> None:
        """Persist current state to disk."""
        self._save_raw(self._data)

    @property
    def snippets(self) -> list[dict]:
        """Return the list of snippet dicts."""
        return self._data.get("snippets", [])

    # -- Subcommand implementations -----------------------------------------

    def add(
        self,
        name: str,
        dax: str,
        category: str = "general",
        tags: list[str] | None = None,
        description: str = "",
    ) -> dict:
        """Add a new DAX snippet. Raises ValueError on duplicate name."""
        slug = _slugify(name)
        if any(s["id"] == slug for s in self.snippets):
            msg = f"Snippet with id '{slug}' already exists"
            raise ValueError(msg)

        ts = _now_iso()
        snippet = {
            "id": slug,
            "name": name,
            "category": category,
            "description": description,
            "dax": dax,
            "tags": tags or [],
            "created": ts,
            "modified": ts,
        }
        self.snippets.append(snippet)
        self._save()
        logger.info("Added snippet: %s (%s)", name, slug)
        return snippet

    def search(self, query: str) -> list[dict]:
        """Search snippets by name, description, tags, or DAX code."""
        query_lower = query.lower()
        results = []
        for s in self.snippets:
            if (
                query_lower in s["name"].lower()
                or query_lower in s.get("description", "").lower()
                or any(query_lower in t.lower() for t in s.get("tags", []))
                or query_lower in s.get("dax", "").lower()
            ):
                results.append(s)
        return results

    def list_snippets(self, category: str | None = None) -> list[dict]:
        """Return all snippets, optionally filtered by category."""
        if category:
            return [s for s in self.snippets if s["category"] == category]
        return list(self.snippets)

    def export(self, fmt: str = "markdown", output_path: Path | None = None) -> str:
        """Export snippets to Markdown or JSON string.

        Args:
            fmt: Output format — 'markdown' or 'json'.
            output_path: If provided, write to this file.

        Returns:
            The exported content as a string.
        """
        if fmt == "json":
            content = json.dumps(self.snippets, indent=2, ensure_ascii=False)
        else:
            content = self._to_markdown()

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content + "\n", encoding="utf-8")
            logger.info("Exported %d snippets to %s", len(self.snippets), output_path)

        return content

    def validate(self) -> list[dict]:
        """Check all snippets for common DAX anti-patterns.

        Anti-patterns detected:
            - Raw division (/) without DIVIDE()
            - FORMAT() usage in measures
            - Missing VAR/RETURN structure
            - CALCULATE without filter modification
        """
        issues: list[dict] = []
        for s in self.snippets:
            dax = s["dax"]
            dax_upper = dax.upper()

            # Raw division without DIVIDE
            # Strip string literals first to avoid false positives like "6/30"
            dax_no_strings = re.sub(r'"[^"]*"', "", dax)
            if re.search(r"(?<![/\*])/(?![/\*])", dax_no_strings) and "DIVIDE" not in dax_upper:
                issues.append(
                    {
                        "id": s["id"],
                        "name": s["name"],
                        "issue": "Uses raw division (/) — use DIVIDE() instead",
                        "severity": "high",
                    }
                )

            # FORMAT() in measures
            if "FORMAT(" in dax_upper:
                issues.append(
                    {
                        "id": s["id"],
                        "name": s["name"],
                        "issue": "Uses FORMAT() — avoid in measures (kills performance)",
                        "severity": "medium",
                    }
                )

            # Missing VAR/RETURN
            if "VAR " not in dax_upper or "RETURN" not in dax_upper:
                issues.append(
                    {
                        "id": s["id"],
                        "name": s["name"],
                        "issue": "Missing VAR/RETURN structure",
                        "severity": "low",
                    }
                )

        return issues

    # -- Private helpers ----------------------------------------------------

    def _to_markdown(self) -> str:
        """Convert snippets to a Markdown reference document."""
        lines = ["# DAX Snippet Reference", ""]
        categories: dict[str, list[dict]] = {}
        for s in self.snippets:
            cat = s.get("category", "general")
            categories.setdefault(cat, []).append(s)

        for cat in sorted(categories):
            lines.append(f"## {cat.replace('-', ' ').title()}")
            lines.append("")
            for s in categories[cat]:
                lines.append(f"### {s['name']}")
                if s.get("description"):
                    lines.append(f"\n{s['description']}\n")
                tags_str = ", ".join(f"`{t}`" for t in s.get("tags", []))
                if tags_str:
                    lines.append(f"**Tags:** {tags_str}\n")
                lines.append("```dax")
                lines.append(s["dax"])
                lines.append("```")
                lines.append("")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI — argument parsing and dispatch
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="dax_manager",
        description="DAX Snippet Manager — store, search, and export DAX patterns.",
    )
    parser.add_argument(
        "--storage",
        type=Path,
        default=DEFAULT_STORAGE,
        help="Path to JSON storage file (default: %(default)s)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # -- add ----------------------------------------------------------------
    add_p = subparsers.add_parser("add", help="Add a new DAX snippet")
    add_p.add_argument("--name", required=True, help="Measure name (e.g. 'YTD Sales')")
    add_p.add_argument("--dax", required=True, help="DAX expression")
    add_p.add_argument("--category", default="general", help="Category (default: general)")
    add_p.add_argument("--tags", nargs="*", default=[], help="Space-separated tags")
    add_p.add_argument("--description", default="", help="Short description")

    # -- search -------------------------------------------------------------
    search_p = subparsers.add_parser("search", help="Search snippets by keyword")
    search_p.add_argument("query", nargs="+", help="Search terms")

    # -- list ---------------------------------------------------------------
    list_p = subparsers.add_parser("list", help="List all snippets")
    list_p.add_argument("--category", default=None, help="Filter by category")

    # -- export -------------------------------------------------------------
    export_p = subparsers.add_parser("export", help="Export snippets")
    export_p.add_argument(
        "--format",
        dest="fmt",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    export_p.add_argument("--output", type=Path, default=None, help="Output file path")

    # -- validate -----------------------------------------------------------
    subparsers.add_parser("validate", help="Check snippets for DAX anti-patterns")

    return parser


def _run_add(manager: DAXManager, args: argparse.Namespace) -> int:
    """Handle the 'add' subcommand."""
    try:
        snippet = manager.add(
            name=args.name,
            dax=args.dax,
            category=args.category,
            tags=args.tags,
            description=args.description,
        )
        print(f"Added: {snippet['name']} (id: {snippet['id']})")
        return 0
    except ValueError as exc:
        logger.error("Failed to add: %s", exc)
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def _run_search(manager: DAXManager, args: argparse.Namespace) -> int:
    """Handle the 'search' subcommand."""
    query = " ".join(args.query)
    results = manager.search(query)

    if not results:
        print(f"No snippets found for '{query}'.")
        # Suggest categories
        categories = sorted({s["category"] for s in manager.snippets})
        if categories:
            print(f"Available categories: {', '.join(categories)}")
        return 0

    print(f"Found {len(results)} snippet(s) for '{query}':\n")
    for s in results:
        print(f"  [{s['id']}] {s['name']}  ({s['category']})")
        tags_str = ", ".join(s.get("tags", []))
        if tags_str:
            print(f"    Tags: {tags_str}")
        print(f"    {s['dax'][:80]}{'...' if len(s['dax']) > 80 else ''}")
        print()
    return 0


def _run_list(manager: DAXManager, args: argparse.Namespace) -> int:
    """Handle the 'list' subcommand."""
    snippets = manager.list_snippets(category=args.category)

    if not snippets:
        label = f" in category '{args.category}'" if args.category else ""
        print(f"No snippets found{label}.")
        return 0

    header = f"{'ID':<30} {'Name':<30} {'Category':<20} {'Tags'}"
    print(header)
    print("-" * len(header))
    for s in snippets:
        tags_str = ", ".join(s.get("tags", [])[:3])
        print(f"{s['id']:<30} {s['name']:<30} {s['category']:<20} {tags_str}")

    print(f"\nTotal: {len(snippets)} snippet(s)")
    return 0


def _run_export(manager: DAXManager, args: argparse.Namespace) -> int:
    """Handle the 'export' subcommand."""
    content = manager.export(fmt=args.fmt, output_path=args.output)

    if args.output:
        print(f"Exported {len(manager.snippets)} snippets to {args.output}")
    else:
        print(content)
    return 0


def _run_validate(manager: DAXManager, _args: argparse.Namespace) -> int:
    """Handle the 'validate' subcommand."""
    issues = manager.validate()

    if not issues:
        print("All snippets passed validation.")
        return 0

    print(f"Found {len(issues)} issue(s):\n")
    for issue in issues:
        severity_icon = {"high": "!!!", "medium": "!!", "low": "!"}.get(
            issue["severity"], "?"
        )
        print(f"  [{severity_icon}] {issue['name']} ({issue['id']})")
        print(f"       {issue['issue']}")
        print()

    return 1


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_COMMANDS = {
    "add": _run_add,
    "search": _run_search,
    "list": _run_list,
    "export": _run_export,
    "validate": _run_validate,
}


def main() -> int:
    """Entry point for the DAX Snippet Manager CLI."""
    parser = _build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )

    manager = DAXManager(storage_path=args.storage)
    handler = _COMMANDS.get(args.command)

    if handler is None:
        parser.print_help()
        return 1

    return handler(manager, args)


if __name__ == "__main__":
    raise SystemExit(main())
