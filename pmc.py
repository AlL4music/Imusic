"""
PMC (b2b.pmc.cz) XML Feed -> CSV converter
Fetches the PMC B2B XML price list and converts it to a simple CSV
compatible with the feed import system.

Note: PMC XML is UTF-16 encoded.

Output: pmc_sklad.csv (semicolon-delimited)
Columns: ITEM_ID;PRODUCTNAME;EAN;Availability
"""

import csv
import sys
import time
import requests
from xml.etree import ElementTree as ET

XML_URL = "http://b2b.pmc.cz/xml/XML_PMCOS.xml"
OUTPUT_FILE = "pmc_sklad.csv"


def fetch_xml(url, timeout=120):
    """Download XML feed with retry logic."""
    for attempt in range(3):
        try:
            print(f"Downloading XML (attempt {attempt + 1})...")
            resp = requests.get(url, timeout=timeout, headers={
                "User-Agent": "All4music-FeedImport/1.0"
            }, verify=False)  # SSL cert issue on b2b.pmc.cz
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
    """Parse UTF-16 XML and extract product data rows."""
    # PMC XML is UTF-16 encoded - decode first
    try:
        xml_text = xml_bytes.decode("utf-16")
    except UnicodeDecodeError:
        # Try UTF-16 LE without BOM
        xml_text = xml_bytes.decode("utf-16-le")

    root = ET.fromstring(xml_text)

    rows = []
    total = 0
    in_stock = 0
    no_ean = 0

    for item in root.iter("SHOP_ITEM"):
        total += 1
        item_id = (item.findtext("ITEM_ID") or "").strip()
        ean = (item.findtext("EAN") or "").strip()
        avail_str = (item.findtext("AVAILABILITY") or "0").strip()

        try:
            availability = int(float(avail_str))
        except ValueError:
            availability = 0

        if availability > 0:
            in_stock += 1

        if not ean:
            no_ean += 1

        if not item_id:
            continue

        productname = (item.findtext("PRODUCTNAME") or "").strip()
        productname = productname.replace(";", ",")

        rows.append({
            "ITEM_ID": item_id,
            "PRODUCTNAME": productname,
            "EAN": ean,
            "Availability": availability
        })

    print(f"Parsed: {total} items, {in_stock} in stock, {no_ean} without EAN")
    return rows


def write_csv(rows, output_file):
    """Write rows to semicolon-delimited CSV."""
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["ITEM_ID", "PRODUCTNAME", "EAN", "Availability"],
            delimiter=";",
            quoting=csv.QUOTE_MINIMAL
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Written: {len(rows)} rows to {output_file}")


def main():
    print("=" * 50)
    print("PMC B2B XML -> CSV Converter")
    print("=" * 50)

    xml_bytes = fetch_xml(XML_URL)
    rows = parse_xml_to_rows(xml_bytes)
    write_csv(rows, OUTPUT_FILE)

    with_stock = sum(1 for r in rows if r["Availability"] > 0)
    with_ean = sum(1 for r in rows if r["EAN"])
    print(f"\nDone! {len(rows)} products, {with_ean} with EAN, {with_stock} in stock")


if __name__ == "__main__":
    main()
