#!/usr/bin/env python3
"""
ESP-Family Product Generator (offline)
======================================
Builds import-ready product records for ESP-family guitars (Edwards, ESP,
E-II, LTD) straight from the Sound Service stock feed, WITHOUT scraping.

It exists so that brands without a live scraper path (notably Edwards, ESP's
Japanese sub-brand) stop showing up as "Unmatched (Prep)" / "not connected"
in the Feed Prep dashboard: every selected feed row becomes a product record
with SKU, name, brand, price, EAN, quantity and a templated HTML description
(reusing the same template as esp_guitar_scraper.py).

Real specs/photos can be backfilled later by running the live scraper
workflow (ESP.yml) where espguitars.com / edwards-guitars.com are reachable.

Usage:
    python generate_esp_family_products.py sound_serivce.csv esp_family_products.csv
    python generate_esp_family_products.py sound_serivce.csv out.csv --brands Edwards
"""

import argparse
import csv
import re
import sys

# Reuse the exact HTML template + description logic the ESP scraper uses, so
# generated pages look identical to the live-scraped ones.
from esp_guitar_scraper import ESPScraper

# Source feed columns (semicolon-delimited, quoted)
COL_SKU = "Item ID"
COL_BRAND = "Značka"
COL_NAME = "Popis"
COL_QTY = "Sklad"
COL_PRICE = "Cena (Dealer)"
COL_EAN = "EAN"
COL_DISCONTINUED = "Ukončené"

DEFAULT_BRANDS = ["Edwards", "ESP", "E-II", "LTD"]

# Suffixes that are catalogue noise, not part of the model/color.
NAME_SUFFIXES = [
    " Original Series", " Series", " Incl. Gigbag", " Incl. Gig Bag",
    " Incl. Case", " L/H", " Guitars", " Guitar",
]

# Tokens that signal the start of the color part of a name. Everything from
# the first all-letters word that isn't a model code onward is treated as
# color. Model codes contain digits, hyphens or slashes (e.g. E-LP-125SD,
# HORIZON NT-7B). This is best-effort and only used for display text.
COLOR_HINT = re.compile(r"^[A-Za-z/]+$")


def strip_brand_prefix(name, brand):
    """Remove a leading brand word (e.g. 'Edwards ', 'E-II ') from the name."""
    name = name.strip()
    for prefix in (f"{brand} ", "ESP ORIGINAL ", "ESP ", "E-II ", "LTD ", "Edwards "):
        if name.upper().startswith(prefix.upper()):
            return name[len(prefix):].strip()
    return name


def split_model_color(name, brand):
    """Best-effort split of a product name into (model, color).

    Model = the leading run of tokens that contain a digit, hyphen or slash
    (the model code). Color = the trailing human-readable color words.
    Falls back to (whole, "") when no clear boundary exists.
    """
    base = strip_brand_prefix(name, brand)
    for suffix in NAME_SUFFIXES:
        base = re.sub(re.escape(suffix) + r"\s*$", "", base, flags=re.IGNORECASE).strip()

    tokens = base.split()
    if not tokens:
        return name.strip(), ""

    model_tokens = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        is_code = bool(re.search(r"[\d/\-]", tok)) or tok.isupper()
        # First token is always part of the model (e.g. ALEXI, HORIZON).
        if i == 0 or is_code:
            model_tokens.append(tok)
            i += 1
        else:
            break

    model = " ".join(model_tokens) if model_tokens else tokens[0]
    color = " ".join(tokens[i:]).strip()
    return model, color


def clean_price(raw):
    if not raw:
        return ""
    raw = raw.strip().strip('"')
    try:
        return f"{float(raw):.2f}"
    except ValueError:
        return raw


def main():
    parser = argparse.ArgumentParser(description="Offline ESP-family product generator")
    parser.add_argument("input_csv", help="Sound Service feed CSV (semicolon-delimited)")
    parser.add_argument("output_csv", help="Output product CSV")
    parser.add_argument("--brands", nargs="*", default=DEFAULT_BRANDS,
                        help=f"Brands to include (default: {' '.join(DEFAULT_BRANDS)})")
    parser.add_argument("--delimiter", default=";", help="Input delimiter (default ';')")
    parser.add_argument("--include-discontinued", action="store_true",
                        help="Include rows flagged Ukončené=1 (default: skip)")
    args = parser.parse_args()

    wanted = {b.upper() for b in args.brands}
    scraper = ESPScraper()  # used only for its offline _generate_html helper

    rows_out = []
    skipped_disc = 0
    with open(args.input_csv, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=args.delimiter)
        for row in reader:
            brand = (row.get(COL_BRAND) or "").strip()
            if brand.upper() not in wanted:
                continue
            if not args.include_discontinued and (row.get(COL_DISCONTINUED) or "").strip() == "1":
                skipped_disc += 1
                continue

            name = (row.get(COL_NAME) or "").strip()
            sku = (row.get(COL_SKU) or "").strip()
            if not sku or not name:
                continue

            model, color = split_model_color(name, brand)
            # No live images available offline; leave blank for later backfill.
            img_urls = ["", "", ""]
            html_desc = scraper._generate_html(brand, model, color, img_urls, specs={})

            rows_out.append({
                "SKU": sku,
                "Brand": brand,
                "Model": model,
                "Color": color,
                "Name": name,
                "Price": clean_price(row.get(COL_PRICE)),
                "EAN": (row.get(COL_EAN) or "").strip(),
                "Quantity": (row.get(COL_QTY) or "0").strip(),
                "Image_1": img_urls[0],
                "Image_2": img_urls[1],
                "Image_3": img_urls[2],
                "HTML_Description": html_desc,
            })

    if not rows_out:
        print("No matching rows found. Check --brands and the input file.", file=sys.stderr)
        sys.exit(1)

    fieldnames = ["SKU", "Brand", "Model", "Color", "Name", "Price", "EAN",
                  "Quantity", "Image_1", "Image_2", "Image_3", "HTML_Description"]
    with open(args.output_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows_out)

    by_brand = {}
    for r in rows_out:
        by_brand[r["Brand"]] = by_brand.get(r["Brand"], 0) + 1
    print(f"Wrote {len(rows_out)} products to {args.output_csv}")
    for b in sorted(by_brand):
        print(f"  {b:<8} {by_brand[b]}")
    if skipped_disc:
        print(f"Skipped {skipped_disc} discontinued rows (use --include-discontinued to keep)")


if __name__ == "__main__":
    main()
