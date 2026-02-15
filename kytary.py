"""
Kytary.com B2B XML Feed → CSV converter
Fetches the Kytary B2B XML price list and converts it to a simple CSV
compatible with the feed import system.

Output: kytary_sklad.csv (semicolon-delimited)
Columns: ProductCode;ProductName;AvailableVolume
"""

import csv
import sys
import time
import requests
from xml.etree import ElementTree as ET

# Kytary B2B feed URL
XML_URL = (
    "https://public.kytary.com/VO/GetPriceListXml2"
    "?hash=TKOgioclbibdvuWunMPAiC1CUXVQ3MsDmrfhGXZqcHRQ%2bmYfR1AW54rT7ZkBe9k9YJslfeHQTcjsca22lPWa%2fQ%3d%3d"
    "&instanceCode=B2B_SK&mode=full"
)

OUTPUT_FILE = "kytary_sklad.csv"


def fetch_xml(url, timeout=300):
    """Download XML feed with retry logic."""
    for attempt in range(3):
        try:
            print(f"Downloading XML (attempt {attempt + 1})...")
            resp = requests.get(url, timeout=timeout, headers={
                "User-Agent": "All4music-FeedImport/1.0"
            })
            resp.raise_for_status()
            print(f"Downloaded: {len(resp.content):,} bytes")
            return resp.content
        except requests.RequestException as e:
            print(f"  Error: {e}")
            if attempt < 2:
                wait = 10 * (attempt + 1)
                print(f"  Retrying in {wait}s...")
                time.sleep(wait)
    print("FATAL: Failed to download XML after 3 attempts")
    sys.exit(1)


def parse_xml_to_rows(xml_bytes):
    """Parse XML and extract product data rows."""
    root = ET.fromstring(xml_bytes)

    # Handle namespace if present
    ns = ""
    if root.tag.startswith("{"):
        ns = root.tag.split("}")[0] + "}"

    rows = []
    total = 0
    in_stock = 0

    for item in root.iter(f"{ns}VOPriceListItem"):
        total += 1
        code = (item.findtext(f"{ns}ProductCode") or "").strip()
        name = (item.findtext(f"{ns}ProductName") or "").strip()
        qty_str = (item.findtext(f"{ns}AvailableVolume") or "0").strip()
        stock_flag = (item.findtext(f"{ns}InStock") or "false").strip().lower()

        # Convert quantity - some may be decimal
        try:
            qty = int(float(qty_str))
        except ValueError:
            qty = 0

        if not code:
            continue

        if stock_flag == "true":
            in_stock += 1

        # Clean name (remove semicolons for CSV compatibility)
        name = name.replace(";", ",")

        rows.append({
            "ProductCode": code,
            "ProductName": name,
            "AvailableVolume": qty
        })

    print(f"Parsed: {total} items, {in_stock} in stock")
    return rows


def write_csv(rows, output_file):
    """Write rows to semicolon-delimited CSV."""
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["ProductCode", "ProductName", "AvailableVolume"],
            delimiter=";",
            quoting=csv.QUOTE_MINIMAL
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Written: {len(rows)} rows to {output_file}")


def main():
    print("=" * 50)
    print("Kytary B2B XML → CSV Converter")
    print("=" * 50)

    xml_bytes = fetch_xml(XML_URL)
    rows = parse_xml_to_rows(xml_bytes)
    write_csv(rows, OUTPUT_FILE)

    # Summary
    with_qty = sum(1 for r in rows if r["AvailableVolume"] > 0)
    print(f"\nDone! {len(rows)} products, {with_qty} with stock > 0")


if __name__ == "__main__":
    main()
