"""Generate sample sales CSV with intentional data quality issues.

Creates a 200-row CSV file with realistic sales data that contains
common data quality problems: missing values, duplicates, outliers,
invalid dates, whitespace in strings, and negative quantities.
"""

import argparse
import csv
import logging
import random
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# --- Constants ---

PRODUCTS: list[str] = [
    "Laptop", "Monitor", "Keyboard", "Mouse", "Headset",
    "Webcam", "Docking Station", "USB Hub", "SSD Drive", "RAM Module",
]

REGIONS: list[str] = ["North", "South", "East", "West", "Central"]

REGIONS_WITH_ISSUES: list[str] = [" North", "South ", " East ", "west", "CENTRAL"]

VALID_DATES: list[str] = [
    "01/15/2024", "02/20/2024", "03/10/2024", "04/05/2024",
    "05/18/2024", "06/22/2024", "07/30/2024", "08/14/2024",
    "09/03/2024", "10/25/2024", "11/11/2024", "12/01/2024",
]

INVALID_DATES: list[str] = [
    "13/25/2024", "00/15/2024", "02/30/2024", "14/01/2024",
    "2024-01-15", "15.03.2024", "not_a_date",
]

COLUMNS: list[str] = [
    "OrderDate", "Region", "Product", "SalesAmount",
    "Quantity", "CustomerID",
]


def generate_row(row_id: int) -> dict[str, str]:
    """Generate a single row of sales data.

    Args:
        row_id: Sequential identifier for the row.

    Returns:
        Dictionary with column names as keys and string values.
    """
    # OrderDate: ~5% invalid
    if random.random() < 0.05:
        order_date = random.choice(INVALID_DATES)
    else:
        order_date = random.choice(VALID_DATES)

    # Region: ~8% with whitespace/case issues
    if random.random() < 0.08:
        region = random.choice(REGIONS_WITH_ISSUES)
    else:
        region = random.choice(REGIONS)

    product = random.choice(PRODUCTS)

    # SalesAmount: ~5% missing, ~2% outlier (999999)
    roll = random.random()
    if roll < 0.05:
        sales_amount = ""
    elif roll < 0.07:
        sales_amount = str(999999)
    else:
        sales_amount = str(round(random.uniform(50, 5000), 2))

    # Quantity: ~3% negative
    if random.random() < 0.03:
        quantity = str(random.randint(-10, -1))
    else:
        quantity = str(random.randint(1, 50))

    # CustomerID: limited pool to create duplicates
    customer_id = f"CUST-{random.randint(1, 80):04d}"

    return {
        "OrderDate": order_date,
        "Region": region,
        "Product": product,
        "SalesAmount": sales_amount,
        "Quantity": quantity,
        "CustomerID": customer_id,
    }


def generate_csv(output_path: Path, num_rows: int = 200) -> None:
    """Generate a CSV file with sample sales data and intentional issues.

    Args:
        output_path: Path where the CSV file will be saved.
        num_rows: Number of rows to generate (default 200).
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, str]] = []
    for i in range(num_rows):
        rows.append(generate_row(i))

    # Add ~3% exact duplicate rows
    num_duplicates = int(num_rows * 0.03)
    for _ in range(num_duplicates):
        duplicate_source = random.choice(rows)
        rows.append(duplicate_source.copy())

    random.shuffle(rows)

    # Add ~5% missing values by randomly blanking cells
    for row in rows:
        if random.random() < 0.05:
            field = random.choice(["OrderDate", "Region", "Product", "Quantity"])
            row[field] = ""

    with output_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    logger.info("Generated %d rows → %s", len(rows), output_path)


def main() -> None:
    """CLI entry point for sample data generation."""
    parser = argparse.ArgumentParser(
        description="Generate sample sales CSV with data quality issues."
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("data/sales_sample.csv"),
        help="Output CSV path (default: data/sales_sample.csv)",
    )
    parser.add_argument(
        "-n", "--num-rows",
        type=int,
        default=200,
        help="Number of rows to generate (default: 200)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    args = parser.parse_args()

    random.seed(args.seed)
    generate_csv(args.output, args.num_rows)


if __name__ == "__main__":
    main()
