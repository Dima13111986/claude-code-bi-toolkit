"""Generate sample sales CSV with intentional data quality issues.

Creates a 200-row dataset with ~5% missing values, ~3% duplicates,
outliers, invalid dates, whitespace issues, and negative quantities
for testing data quality checks before Power BI import.
"""

import argparse
import logging
import random
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

PRODUCTS = [
    "Laptop", "Monitor", "Keyboard", "Mouse", "Headset",
    "Webcam", "Docking Station", "USB Hub", "SSD Drive", "RAM Module",
]
REGIONS = ["North", "South", "East", "West", "Central"]


def generate_sales_data(num_rows: int = 200, seed: int = 42) -> pd.DataFrame:
    """Generate a sales DataFrame with intentional quality issues.

    Args:
        num_rows: Number of rows to generate.
        seed: Random seed for reproducibility.

    Returns:
        DataFrame with columns: OrderDate, Region, Product,
        SalesAmount, Quantity, CustomerID.
    """
    random.seed(seed)

    data: dict[str, list] = {
        "OrderDate": [],
        "Region": [],
        "Product": [],
        "SalesAmount": [],
        "Quantity": [],
        "CustomerID": [],
    }

    for i in range(num_rows):
        # OrderDate — ~3% invalid dates
        if random.random() < 0.03:
            data["OrderDate"].append("13/25/2024")
        elif random.random() < 0.05:
            data["OrderDate"].append(None)
        else:
            month = random.randint(1, 12)
            day = random.randint(1, 28)
            data["OrderDate"].append(f"{month:02d}/{day:02d}/2024")

        # Region — ~5% with leading/trailing whitespace
        region = random.choice(REGIONS)
        if random.random() < 0.05:
            region = f" {region} "
        if random.random() < 0.05:
            data["Region"].append(None)
        else:
            data["Region"].append(region)

        # Product
        data["Product"].append(random.choice(PRODUCTS))

        # SalesAmount — ~5% nulls, ~2% outliers
        if random.random() < 0.05:
            data["SalesAmount"].append(None)
        elif random.random() < 0.02:
            data["SalesAmount"].append(999999.99)
        else:
            data["SalesAmount"].append(round(random.uniform(50, 2000), 2))

        # Quantity — ~3% negative
        if random.random() < 0.03:
            data["Quantity"].append(-random.randint(1, 10))
        else:
            data["Quantity"].append(random.randint(1, 50))

        # CustomerID — limited pool for duplicates
        data["CustomerID"].append(f"CUST-{random.randint(1, 150):04d}")

    df = pd.DataFrame(data)

    # Add ~3% exact duplicate rows
    num_dupes = int(num_rows * 0.03)
    if num_dupes > 0 and len(df) > 0:
        dupes = df.sample(n=num_dupes, random_state=seed)
        df = pd.concat([df, dupes], ignore_index=True)

    return df


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
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    args.output.parent.mkdir(parents=True, exist_ok=True)

    df = generate_sales_data(num_rows=args.num_rows, seed=args.seed)
    df.to_csv(args.output, index=False)
    logger.info("Generated %d rows → %s", len(df), args.output)


if __name__ == "__main__":
    main()
