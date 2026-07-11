#!/usr/bin/env python3
"""
Ibanez Build-Sheet Product Generator (offline)
==============================================
Turns an Ibanez factory "Build Sheet" (.xlsx) into import-ready product
records in the SAME 12-column schema that create_products.js consumes
(SKU, Brand, Model, Color, Name, Price, EAN, Quantity, Image_1..3,
HTML_Description).

Unlike the ESP-family generator — which only has a name + price to work
with and therefore emits a templated stub — the Ibanez build sheet carries
full marketing copy, a feature list with per-feature explanations, and a
complete spec table. This script uses all of it to build a rich HTML
description, while reusing the exact same CSS / container markup as
esp_guitar_scraper.py so the resulting product page looks native on the shop.

SKU convention: OpenCart / the Ibanez availability feed (Ibanez.csv) key
products by "<MODEL>-<COLORCODE>" (e.g. PT32-BBK). We follow that here:
RGR8820QM + BRE -> RGR8820QM-BRE.

Notes
  * Price and stock are NOT on the build sheet, so Price=0 / Quantity=0.
    create_products.js creates products DISABLED (staged) by default, so you
    set the price and publish them yourself before they go live.
  * Images are "TBA" on pre-release sheets -> left blank for later backfill.

Usage
    python generate_ibanez_product.py <build_sheet.xlsx> [out.csv] [--price N]
    # default out.csv = ibanez_products.csv
    # --price 4500            set the price for every product in the sheet
    # --price RGR8820QM-BRE=4500   set the price for one SKU (repeatable)
    node create_products.js --file ibanez_products.csv            # dry run
    node create_products.js --file ibanez_products.csv --commit    # create
"""

import csv
import html
import os
import re
import sys

import openpyxl

# The exact CSS the ESP scraper emits (esp_guitar_scraper.HTML_TEMPLATE), inlined
# so Ibanez product pages render identically to the rest of the catalogue without
# importing the scraper's scraping-only dependencies (bs4/requests).
STYLE = (
    "<style>\n"
    ".product-description-container{font-family:'Roboto',sans-serif;color:#374151}"
    ".product-description-container h3,.product-description-container h4{font-family:'Barlow',sans-serif;font-weight:900;letter-spacing:-.025em;color:#111827}"
    ".product-description-container ul{list-style-type:disc;margin-left:1.5rem;margin-bottom:1rem;padding-left:1rem}"
    ".product-description-container li{margin-bottom:.25rem}"
    ".product-description-container .prose{line-height:1.75}"
    ".features-3col-section{text-align:center;padding:2rem 0}"
    ".features-3col-section .main-image img{border-radius:.75rem;box-shadow:0 10px 15px -3px rgba(0,0,0,.1);width:100%;max-width:800px;margin:0 auto 2rem auto}"
    ".features-3col-section .main-text{max-width:800px;margin:0 auto 3rem auto}"
    ".features-3col-section .main-text h3{font-size:2.25rem;margin-bottom:1rem}"
    ".features-3col-section .columns-container{display:grid;gap:2rem;max-width:1200px;margin:0 auto}"
    ".features-3col-section .columns-container.cols-3{grid-template-columns:repeat(3,1fr)}"
    ".features-3col-section .feature-item{text-align:left}"
    ".features-3col-section .feature-item svg{width:48px;height:48px;margin-bottom:1rem;color:#e7284d}"
    ".features-3col-section .feature-item h4{font-size:1.25rem;font-weight:700;margin-bottom:.5rem}"
    ".desc-section{display:grid;grid-template-columns:1fr 1fr;gap:2rem;align-items:center;margin-bottom:2rem}"
    ".desc-section.image-layout-left .desc-image{order:1}.desc-section.image-layout-left .desc-text{order:2}"
    ".desc-section.image-layout-right .desc-image{order:2}.desc-section.image-layout-right .desc-text{order:1}"
    ".desc-image{border-radius:.75rem;overflow:hidden;box-shadow:0 10px 15px -3px rgba(0,0,0,.1);background-color:#f9fafb}"
    ".desc-image img{width:100%;height:100%;display:block;object-fit:contain}"
    ".desc-text h3{font-size:1.875rem;margin-bottom:1rem}"
    "@media(max-width:768px){.desc-section{grid-template-columns:1fr}.features-3col-section .columns-container.cols-3{grid-template-columns:1fr}}"
    "\n</style>"
)


def norm(h):
    return re.sub(r"\s+", " ", str(h).replace("\n", " ")).strip() if h is not None else ""


def clean(v):
    """Return a stripped string, treating the sheet's '-' placeholder as empty."""
    if v is None:
        return ""
    s = str(v).strip()
    return "" if s in ("-", "—", "TBA", "N/A") else s


def read_sheet(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    header = [norm(h) for h in rows[0]]
    out = []
    for data in rows[1:]:
        if not any(c is not None and str(c).strip() for c in data):
            continue
        rec = {}
        for h, v in zip(header, data):
            if h and h not in rec:  # first column wins on duplicate headers
                rec[h] = v
        # A real product row has a model code.
        if clean(rec.get("MODEL")):
            out.append(rec)
    return out


def parse_feature_blocks(copy_text):
    """Parse the '- Title\\n  explanation' blocks under ****...**** headers.

    Returns (features, special_features) as lists of (title, body) tuples.
    """
    if not copy_text:
        return [], []
    features, special = [], []
    bucket = None
    title, body = None, []

    def flush(target):
        if title and target is not None:
            target.append((title.strip(), " ".join(body).strip()))

    for raw in str(copy_text).splitlines():
        line = raw.strip()
        if not line:
            continue
        low = line.lower().strip("* ")
        if line.startswith("****") and "special feature" in low:
            flush(bucket)
            title, body = None, []
            bucket = special
            continue
        if line.startswith("****") and "product feature" in low:
            flush(bucket)
            title, body = None, []
            bucket = features
            continue
        if line.startswith("- ") and bucket is not None:
            flush(bucket)
            title, body = line[2:].strip(), []
        elif bucket is not None and title:
            body.append(line)
    flush(bucket)
    return features, special


def li(label, value):
    v = clean(value)
    return f"<li>{html.escape(label)} - {html.escape(v)}</li>" if v else ""


def build_html(rec, img_urls=None):
    brand = "Ibanez"
    model = clean(rec.get("MODEL"))
    color = clean(rec.get("Color Name")) or clean(rec.get("COLOR"))
    grade = clean(rec.get("Grade"))
    series = clean(rec.get("Series"))
    category = clean(rec.get("Category"))
    # Prefer discovered/servable image URLs; fall back to build-sheet fields.
    img_urls = (img_urls or []) + ["", "", ""]
    img1 = img_urls[0] or clean(rec.get("Product Image_1"))
    img2 = img_urls[1] or clean(rec.get("Product Image_2"))
    img3 = img_urls[2] or clean(rec.get("Product Image_3"))

    features, special = parse_feature_blocks(rec.get("Copy") or rec.get("Product_Features"))

    # ---- intro paragraph: the build-sheet's own overview copy (before the
    # ****Product Features**** marker), lightly cleaned. ----
    copy = str(rec.get("Copy") or "")
    intro = copy.split("****", 1)[0]
    intro_paras = [p.strip() for p in intro.split("\n\n") if p.strip() and p.strip() != model]
    intro_html = "".join(f"<p>{html.escape(p)}</p>" for p in intro_paras)

    subtitle = " · ".join([x for x in (grade, category, "Made in " + clean(rec.get("Country of origin"))
                                       if clean(rec.get("Country of origin")) else "") if x])

    # ---- three highlight columns (first three product features) ----
    cols = []
    for t, b in features[:3]:
        cols.append(
            '<div class="feature-item">'
            '<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" '
            'fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" '
            'stroke-linejoin="round"><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 '
            '2 12s4.477 10 10 10z"></path><path d="m9 12 2 2 4-4"></path></svg>'
            f'<h4>{html.escape(t)}</h4>'
            f'<div class="prose max-w-none">{html.escape(b)}</div></div>'
        )
    cols_html = "\n".join(cols)

    # ---- full feature list with explanations ----
    feat_items = "\n".join(
        f"<li><strong>{html.escape(t)}</strong>" + (f" — {html.escape(b)}" if b else "") + "</li>"
        for t, b in features
    )
    special_items = "\n".join(
        f"<li><strong>{html.escape(t)}</strong>" + (f" — {html.escape(b)}" if b else "") + "</li>"
        for t, b in special
    )

    # ---- specification groups ----
    neck_thk = " / ".join(x for x in [
        f"{clean(rec.get('Neck thickness (1st fret, mm)'))}mm @1st" if clean(rec.get('Neck thickness (1st fret, mm)')) else "",
        f"{clean(rec.get('Neck thickness (12th fret, mm)'))}mm @12th" if clean(rec.get('Neck thickness (12th fret, mm)')) else "",
    ] if x)
    scale = " / ".join(x for x in [
        f'{clean(rec.get("Scale (inch)"))}"' if clean(rec.get("Scale (inch)")) else "",
        f'{clean(rec.get("Scale (mm)"))}mm' if clean(rec.get("Scale (mm)")) else "",
    ] if x)
    nut_w = " / ".join(x for x in [
        f'{clean(rec.get("Nut width (inch)"))}"' if clean(rec.get("Nut width (inch)")) else "",
        f'{clean(rec.get("Nut width (mm)"))}mm' if clean(rec.get("Nut width (mm)")) else "",
    ] if x)
    fb_radius = " / ".join(x for x in [
        f'{clean(rec.get("Fretboard Radius (inch)"))}"' if clean(rec.get("Fretboard Radius (inch)")) else "",
        f'{clean(rec.get("Fretboard Radius (mm)"))}mm' if clean(rec.get("Fretboard Radius (mm)")) else "",
    ] if x)
    body_wood = " / ".join(x for x in [
        f'{clean(rec.get("Body Top material (For Solid)"))} top' if clean(rec.get("Body Top material (For Solid)")) else "",
        f'{clean(rec.get("Body Material (For Solid)"))} body' if clean(rec.get("Body Material (For Solid)")) else "",
    ] if x)

    specs_1 = "\n".join(x for x in [
        li("Body", body_wood),
        li("Neck type", rec.get("Neck Type")),
        li("Neck material", rec.get("Neck Material")),
        li("Neck joint", rec.get("Neck Joint")),
        li("Neck finish", rec.get("Neck finish")),
        li("Neck thickness", neck_thk),
        li("Scale", scale),
        li("Fretboard", rec.get("Fretboard")),
        li("Fretboard radius", fb_radius),
        li("Frets", (clean(rec.get("Number of fret")) + ", " if clean(rec.get("Number of fret")) else "") + clean(rec.get("Fret Type"))),
        li("Fret edge treatment", rec.get("Fret edge treatment")),
        li("Inlay", rec.get("Inlay")),
        li("Nut width", nut_w),
        li("Number of strings", rec.get("Number of Strings")),
        li("Body finish", rec.get("Body finish")),
        li("Country of origin", rec.get("Country of origin")),
    ] if x)

    specs_2 = "\n".join(x for x in [
        li("Bridge", rec.get("Bridge")),
        li("Nut", rec.get("Nut")),
        li("Machine heads", rec.get("Machine Head")),
        li("Hardware color", rec.get("Hardware color")),
        li("Neck pickup", rec.get("Neck Pickup")),
        li("Bridge pickup", rec.get("Bridge Pickup")),
        li("Electronics", rec.get("Active or Passive")),
        li("Controls", rec.get("Controls, Pickup selector")),
        li("Switching", rec.get("Other Switches")),
        li("String spacing", (clean(rec.get("String spacing (mm)")) + "mm") if clean(rec.get("String spacing (mm)")) else ""),
        li("Side dot inlay", rec.get("Side Dot Inlay")),
        li("Strap lock", rec.get("Strap Lock")),
        li("Strings", rec.get("Special Strings") or rec.get("String Gauges (from top to bottom)")),
        li("String gauges", rec.get("String Gauges (from top to bottom)")),
        li("Tuning", rec.get("Tuning (from top to bottom)")),
        li("Case / bag", rec.get("Included case/bag")),
        li("Also included", rec.get("Other item(s) included")),
    ] if x)

    main_img = f'<div class="main-image"><img src="{html.escape(img1)}" alt="{html.escape(brand + " " + model + " " + color)}" loading="lazy"></div>' if img1 else ""
    img2_tag = f'<img src="{html.escape(img2)}" alt="{html.escape(brand + " " + model)}" loading="lazy">' if img2 else ""
    img3_tag = f'<img src="{html.escape(img3)}" alt="{html.escape(brand + " " + model)}" loading="lazy">' if img3 else ""

    parts = [STYLE, '<div class="product-description-container">']
    parts.append('<section class="features-3col-section">')
    parts.append('<div class="main-text">')
    parts.append(f'<h3>{html.escape(brand)} {html.escape(model)}</h3>')
    if color:
        parts.append(f'<div class="prose max-w-none"><b>{html.escape(color)}</b></div>')
    if subtitle:
        parts.append(f'<div class="prose max-w-none">{html.escape(subtitle)}</div>')
    if intro_html:
        parts.append(f'<div class="prose max-w-none" style="text-align:left">{intro_html}</div>')
    parts.append('</div>')
    parts.append(main_img)
    if cols_html:
        parts.append(f'<div class="columns-container cols-3">\n{cols_html}\n</div>')
    parts.append('</section>')

    if feat_items:
        parts.append('<section class="desc-section image-layout-left">')
        parts.append(f'<div class="desc-image fit-contain" style="height:450px;max-height:450px;">{img2_tag}</div>')
        parts.append(f'<div class="desc-text"><h3>Features</h3><div class="prose max-w-none"><ul>\n{feat_items}\n</ul></div></div>')
        parts.append('</section>')

    if special_items:
        parts.append('<section class="desc-section image-layout-right">')
        parts.append(f'<div class="desc-image fit-contain" style="height:450px;max-height:450px;">{img3_tag}</div>')
        parts.append(f'<div class="desc-text"><h3>Special Features</h3><div class="prose max-w-none"><ul>\n{special_items}\n</ul></div></div>')
        parts.append('</section>')

    if specs_1:
        parts.append('<section class="desc-section image-layout-left">')
        parts.append('<div class="desc-image fit-contain" style="height:450px;max-height:450px;"></div>')
        parts.append(f'<div class="desc-text"><h3>Specifications</h3><div class="prose max-w-none"><ul>\n{specs_1}\n</ul></div></div>')
        parts.append('</section>')

    if specs_2:
        parts.append('<section class="desc-section image-layout-right">')
        parts.append('<div class="desc-image fit-contain" style="height:450px;max-height:450px;"></div>')
        parts.append(f'<div class="desc-text"><h3>Electronics &amp; Hardware</h3><div class="prose max-w-none"><ul>\n{specs_2}\n</ul></div></div>')
        parts.append('</section>')

    parts.append('</div>')
    return "\n".join(parts)


def find_images(sku, image_dir):
    """Discover product photos for a SKU by convention.

    Looks for '<image_dir>/<sku-lower>-*.{jpg,jpeg,png,webp}' (sorted, so
    -1 is the main image) and returns their OpenCart-relative paths, i.e.
    with the leading 'image/' stripped: 'catalog/ibanez/rgr8820qm-bre-1.jpg'.
    """
    if not image_dir or not os.path.isdir(image_dir):
        return []
    pat = re.compile(rf"^{re.escape(sku.lower())}-\d+\.(jpe?g|png|webp)$", re.IGNORECASE)
    files = sorted(f for f in os.listdir(image_dir) if pat.match(f))
    rel = []
    for f in files:
        p = os.path.join(image_dir, f).replace(os.sep, "/")
        rel.append(re.sub(r"^\.?/?image/", "", p))  # OpenCart path is relative to image/
    return rel


def build_record(rec, prices=None, image_dir="image/catalog/ibanez"):
    model = clean(rec.get("MODEL"))
    color_code = clean(rec.get("COLOR"))
    color_name = clean(rec.get("Color Name"))
    grade = clean(rec.get("Grade"))
    sku = f"{model}-{color_code}" if color_code else model

    name_bits = ["Ibanez", model]
    if grade:
        name_bits.append(grade)
    if color_name:
        name_bits.append(color_name)
    desc = clean(rec.get("Description"))
    if desc and "CASE" in desc.upper():
        name_bits.append("(with Case)")
    name = " ".join(name_bits)

    # Price isn't on the build sheet. Accept it via --price SKU=VALUE (or a bare
    # VALUE for a single-product sheet); default 0.00 -> product created staged.
    prices = prices or {}
    raw_price = prices.get(sku, prices.get("*", "0"))
    try:
        price = f"{float(raw_price):.2f}"
    except (TypeError, ValueError):
        price = "0.00"

    # Discover photos by convention (image/catalog/ibanez/<sku>-N.jpg). These
    # OpenCart-relative paths go in the CSV; their servable /image/... URLs are
    # embedded in the HTML description.
    imgs = find_images(sku, image_dir)
    imgs3 = (imgs + ["", "", ""])[:3]
    servable = ["/image/" + p if p else "" for p in imgs3]

    return {
        "SKU": sku,
        "Brand": "Ibanez",
        "Model": model,
        "Color": color_name or color_code,
        "Name": name,
        "Price": price,              # from --price; 0.00 => created staged
        "EAN": clean(rec.get("EAN")),
        "Quantity": "0",             # not on build sheet
        "Image_1": imgs3[0] or clean(rec.get("Product Image_1")),
        "Image_2": imgs3[1] or clean(rec.get("Product Image_2")),
        "Image_3": imgs3[2] or clean(rec.get("Product Image_3")),
        "HTML_Description": build_html(rec, servable),
    }


def parse_prices(tokens):
    """Parse --price args: 'SKU=4500' entries, or a bare '4500' applied to all."""
    prices = {}
    for t in tokens:
        if "=" in t:
            sku, val = t.split("=", 1)
            prices[sku.strip()] = val.strip()
        else:
            prices["*"] = t.strip()
    return prices


def _take_opt(argv, name, default):
    """Pop a repeatable '--name VALUE' option; return the list of values."""
    vals = []
    while name in argv:
        i = argv.index(name)
        if i + 1 < len(argv):
            vals.append(argv[i + 1])
            del argv[i:i + 2]
        else:
            del argv[i]
    return vals if vals else default


def main():
    argv = sys.argv[1:]
    prices_tokens = _take_opt(argv, "--price", [])
    image_dir = _take_opt(argv, "--image-dir", ["image/catalog/ibanez"])[-1]
    if not argv:
        print(__doc__)
        sys.exit(1)
    in_path = argv[0]
    out_path = argv[1] if len(argv) > 1 else "ibanez_products.csv"
    prices = parse_prices(prices_tokens)

    records = [build_record(r, prices, image_dir) for r in read_sheet(in_path)]
    if not records:
        print("No product rows found in build sheet.", file=sys.stderr)
        sys.exit(1)

    fieldnames = ["SKU", "Brand", "Model", "Color", "Name", "Price", "EAN",
                  "Quantity", "Image_1", "Image_2", "Image_3", "HTML_Description"]
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(records)

    print(f"Wrote {len(records)} product(s) to {out_path}")
    for r in records:
        imgs = [r[k] for k in ("Image_1", "Image_2", "Image_3") if r[k]]
        print(f"  {r['SKU']:<16} {r['Name']}  (EAN {r['EAN']}, {len(imgs)} image(s))")


if __name__ == "__main__":
    main()
