"""
Muziker (MuzMuz) CSV Feed Fetcher
Downloads the Muziker B2B CSV feed and saves a clean copy
with only the columns needed for stock import.

Output: muziker_sklad.csv (semicolon-delimited)
Columns: EAN;Code;StockQTY
"""

import csv
import io
import sys
import time
import requests

CSV_URL = "https://pyfeed.muzmuz.tech/feeds/output/bjfifkwodvbba3124emkhfpzf.csv"
OUTPUT_FILE = "muziker_sklad.csv"


def fetch_csv(url, timeout=120):
    """Download CSV feed with retry logic."""
    for attempt in range(3):
        try:
            print(f"Downloading CSV (attempt {attempt + 1})...")
            resp = requests.get(url, timeout=timeout, headers={
                "User-Agent": "All4music-FeedImport/1.0"
            })
            resp.raise_for_status()
            print(f"Downloaded: {len(resp.content):,} bytes")
            return resp.text
        except requests.RequestException as e:
            print(f"  Error: {e}")
            if attempt < 2:
                wait = 10 * (attempt + 1)
                print(f"  Retrying in {wait}s...")
                time.sleep(wait)
    print("FATAL: Failed to download CSV after 3 attempts")
    sys.exit(1)


def process_csv(csv_text):
    """Parse source CSV and extract needed columns."""
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = []
    total = 0
    in_stock = 0

    for row in reader:
        total += 1
        ean = (row.get("EAN") or "").strip()
        code = (row.get("Code") or "").strip()
        qty_str = (row.get("StockQTY") or "0").strip()

        try:
            qty = int(float(qty_str))
        except ValueError:
            qty = 0

        if qty > 0:
            in_stock += 1

        if not ean:
            continue

        rows.append({
            "EAN": ean,
            "Code": code,
            "StockQTY": qty
        })

    print(f"Parsed: {total} items, {in_stock} in stock")
    return rows


def write_csv(rows, output_file):
    """Write rows to semicolon-delimited CSV."""
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["EAN", "Code", "StockQTY"],
            delimiter=";",
            quoting=csv.QUOTE_MINIMAL
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Written: {len(rows)} rows to {output_file}")


def main():
    print("=" * 50)
    print("Muziker CSV Feed Fetcher")
    print("=" * 50)

    csv_text = fetch_csv(CSV_URL)
    rows = process_csv(csv_text)
    write_csv(rows, OUTPUT_FILE)

    with_stock = sum(1 for r in rows if r["StockQTY"] > 0)
    print(f"\nDone! {len(rows)} products, {with_stock} in stock")


if __name__ == "__main__":
    main()
