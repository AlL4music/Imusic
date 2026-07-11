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


def _norm(s):
    return re.sub(r"\s+", " ", str(s)).strip()


# ---------------------------------------------------------------------------
# Slovak translation tables. Structured parts (headings, spec labels, common
# values) translate deterministically. The narrative copy (intro paragraphs,
# feature explanations) is a translation memory: exact Ibanez boilerplate is
# translated, anything not yet in the map falls back to the English text, so a
# page is never broken — just extend _SK_NARRATIVE as new copy appears.
# ---------------------------------------------------------------------------
SK_HEADINGS = {
    "Features": "Vlastnosti",
    "Special Features": "Špeciálne vlastnosti",
    "Specifications": "Špecifikácie",
    "Electronics & Hardware": "Elektronika a hardvér",
}
SK_SPEC_LABELS = {
    "Body": "Telo", "Neck type": "Typ krku", "Neck material": "Materiál krku",
    "Neck joint": "Spoj krku", "Neck finish": "Povrch krku", "Neck thickness": "Hrúbka krku",
    "Scale": "Menzúra", "Fretboard": "Hmatník", "Fretboard radius": "Rádius hmatníka",
    "Frets": "Pražce", "Fret edge treatment": "Úprava hrán pražcov", "Inlay": "Inlay",
    "Nut width": "Šírka nultého pražca", "Number of strings": "Počet strún",
    "Body finish": "Povrch tela", "Country of origin": "Krajina pôvodu",
    "Bridge": "Mostík", "Nut": "Nultý pražec", "Machine heads": "Ladiace mechaniky",
    "Hardware color": "Farba hardvéru", "Neck pickup": "Krčný snímač",
    "Bridge pickup": "Mostíkový snímač", "Electronics": "Elektronika",
    "Controls": "Ovládanie", "Switching": "Prepínanie", "String spacing": "Rozostup strún",
    "Side dot inlay": "Bočné bodky", "Strap lock": "Strap lock", "Strings": "Struny",
    "String gauges": "Hrúbky strún", "Tuning": "Ladenie", "Case / bag": "Puzdro",
    "Also included": "Ďalej obsahuje",
}
SK_SPEC_VALUES = {
    "Bolt-on": "Skrutkovaný (Bolt-on)", "Set-in": "Vlepený (Set-in)", "Neck-through": "Prechádzajúci krkom",
    "Active": "Aktívna", "Passive": "Pasívna", "Rosewood": "Palisander", "Ebony": "Eben",
    "Satin Polyurethane": "Saténový polyuretán", "Gloss Polyester": "Lesklý polyester",
    "Locking": "Uzamykateľný", "JAPAN": "Japonsko", "Japan": "Japonsko",
    "INDONESIA": "Indonézia", "CHINA": "Čína", "Gold": "Zlatá", "Black": "Čierna",
    "Chrome": "Chrómová", "Cosmo Black": "Cosmo Black",
}
# Locative case for the "Vyrobené v ..." phrase (SK grammar).
SK_COUNTRY_LOC = {"Japonsko": "Japonsku", "Indonézia": "Indonézii", "Čína": "Číne", "USA": "USA"}
_SK_NARRATIVE = {
    "The RG is the most recognizable and distinctive guitar in the Ibanez line. Three decades of metal have forged this high-performance machine, honing it for both speed and strength. Whether you favor a hardtail (fixed) bridge or our industry-leading locking tremolo system, the RG is a precision instrument.":
        "RG je najznámejšia a najvýraznejšia gitara v ponuke Ibanez. Tri desaťročia metalu vykovali tento vysokovýkonný nástroj a vybrúsili ho pre rýchlosť aj silu. Či už uprednostňujete pevný (hardtail) mostík alebo náš špičkový uzamykateľný tremolo systém, RG je precízny nástroj.",
    "- Axe Design Lab - Ibanez has been creating innovations which do not only fit the unique demands of players from that period, but also eventually turn into industrial standards, such as 7 string, 8 string and Multi scale guitars. All these started from our attitude to be “Innovative, Cutting-Edge and Pioneer”. Axe Design Lab is the series fully represents this attitude.":
        "Axe Design Lab – Ibanez neustále prináša inovácie, ktoré nielen zodpovedajú jedinečným požiadavkám hráčov danej doby, ale sa nakoniec stávajú aj priemyselnými štandardmi, ako sú 7-strunové, 8-strunové a multi-menzúrové gitary. Všetko to vychádza z nášho prístupu byť „inovatívni, priekopnícki a na špici“. Séria Axe Design Lab tento prístup plne reprezentuje.",
    "- j.custom - Ibanez j.custom guitars are manufactured by an elite group of highly skilled luthiers trained in producing instruments of uncompromised quality. The j.custom designation represents every advance in design and technology Ibanez has developed over the decades: the best woods, neck, fret treatments, in-demand pickup, and top-quality hardware. Each is masterfully crafted to the highest standards to ensure unparalleled sound, maximum playability and exquisite beauty.":
        "j.custom – Gitary Ibanez j.custom vyrába elitná skupina vysoko zručných luthierov školených vo výrobe nástrojov nekompromisnej kvality. Označenie j.custom predstavuje každý pokrok v dizajne a technológiách, ktoré Ibanez za desaťročia vyvinul: najlepšie drevá, krk, úpravu pražcov, žiadané snímače a špičkový hardvér. Každý kus je majstrovsky zhotovený podľa najvyšších štandardov, aby zaručil neprekonateľný zvuk, maximálnu hrateľnosť a výnimočnú krásu.",
    "Super Wizard AS 5pc Maple/Wenge neck": "5-dielny krk Super Wizard AS (Maple/Wenge)",
    "Rosewood fretboard": "Palisandrový hmatník",
    "Jumbo frets with j.custom fret edge treatment": "Jumbo pražce s j.custom úpravou hrán",
    "Quilted Maple (4mm) top / Alder body": "Vrchná doska Quilted Maple (4 mm) / telo z jelše",
    "Fishman® Fluence™ Modern Humbucker Ceramic pickups": "Snímače Fishman® Fluence™ Modern Humbucker Ceramic",
    "Gotoh® machine heads": "Ladiace mechaniky Gotoh®",
    "Lo-Pro Edge tremolo": "Tremolo Lo-Pro Edge",
    "Fishman® Fluence™ Voicing switch": "Prepínač Fishman® Fluence™ Voicing",
    "Luminlay side dots": "Bočné bodky Luminlay",
    "Gotoh® Strap lock pins": "Kolíky Gotoh® strap lock",
    "Hardshell case included": "Súčasťou je tvrdé puzdro",
    "This Super Wizard AS neck has a more rounded shape towards the bass side, while still retaining the overall thickness of the Super Wizard profile– 17mm at nut and 19mm at 12th fret. This asymmetric shape provides a more comfortable grip and natural feel that makes techniques like sweeping and string skipping much easier.":
        "Asymetrický tvar je zaoblenejší na basovej strane a zároveň si zachováva celkovú hrúbku profilu Super Wizard (17 mm pri nultom, 19 mm pri 12. pražci). Poskytuje pohodlnejší úchop a prirodzený pocit, vďaka ktorému sú techniky ako sweeping a preskakovanie strún oveľa jednoduchšie.",
    "Rosewood fretboard provides a well-balanced solid tone with a focused mid range.":
        "Palisandrový hmatník poskytuje vyvážený, plný tón so zameraním na stredy.",
    "The wide and tall fret-type offers a quick response, good articulation when playing chords and clear tone when playing single notes. The j.custom fret edge treatment provides the ultimate smooth touch around every single fret.":
        "Široký a vysoký typ pražcov ponúka rýchlu odozvu, dobrú artikuláciu pri akordoch a čistý tón. j.custom úprava hrán zaručuje dokonale hladký pocit pri každom pražci.",
    "The Quilted Maple top displaying a beautiful wood grain and the Alder body deliver a well-balanced bright tone, enriched resonance and sustain.":
        "Prešívaný javor s nádhernou kresbou dreva a telo z jelše prinášajú vyvážený jasný tón, bohatšiu rezonanciu a sustain.",
    "The Fishman® Fluence™ Modern Humbucker pickups provide an aggressive tone and a powerful attack without excess noise.":
        "Snímače Fishman® Fluence™ Modern Humbucker poskytujú agresívny tón a razantný útok bez nadmerného šumu.",
    "Gotoh® machine heads provide superior precision, a smooth feel, and excellent tuning accuracy.":
        "Ladiace mechaniky Gotoh® poskytujú vynikajúcu presnosť, plynulý chod a výbornú stabilitu ladenia.",
    "The legendary Lo-Pro Edge bridge offers maximum playing comfort with its streamlined profile and recessed fine tuners. Locking studs contribute to tuning stability.":
        "Legendárny mostík Lo-Pro Edge ponúka maximálne pohodlie pri hraní vďaka nízkemu profilu a zapusteným jemným ladičkám. Uzamykateľné čapy prispievajú k stabilite ladenia.",
    "The Voicing switch allows the pickups to switch from a modern, active high output sound to a crisp, clean and fluid sound.":
        "Prepínač Voicing umožňuje snímačom prepnúť z moderného aktívneho zvuku s vysokým výstupom na čistý a plynulý zvuk.",
    "The Luminlay side dot position marks make it easy for players to see fretboard position marks when performing on dark stages.":
        "Bočné orientačné bodky Luminlay uľahčujú sledovanie pozície na hmatníku pri hraní na tmavých pódiách.",
    "Gotoh® Strap lock pins protect your guitar from falling under tough stage performance.":
        "Kolíky Gotoh® strap lock chránia gitaru pred pádom pri náročných vystúpeniach.",
    "Ibanez Hardshell case gives extreme protection for your beloved instrument.":
        "Tvrdé puzdro Ibanez poskytuje extrémnu ochranu vášho nástroja.",
    "Special j.custom Neck": "Špeciálny j.custom krk",
    "All Access Neck Joint": "All Access Neck Joint",
    "Chambered body (RG)": "Komorované telo (RG)",
    "Deep and beveled lower horn scoop": "Hlboko a skosene vyrezaný spodný roh",
    "j.custom Super Wizard neck includes jumbo frets finished with our j.custom special fret edge treatment for a super smooth and comfortable performance. The ”Velvetouch” finish on the back of the neck ensures a ”just right” feel and easy playability.":
        "Krk Super Wizard obsahuje jumbo pražce so špeciálnou j.custom úpravou hrán pre super hladký a pohodlný výkon. Povrchová úprava „Velvetouch“ na zadnej strane krku zaručuje ideálny pocit a jednoduchú hrateľnosť.",
    "All Access Neck Joint offers superior playability at the high frets.":
        "Spoj krku All Access Neck Joint ponúka vynikajúcu hrateľnosť vo vysokých pražcoch.",
    "The chambered body not only contributes to a lighter overall weight, but also adds just the right amount of bottom and clarity, which is preferred by today’s metal players.":
        "Komorované telo prispieva k nižšej hmotnosti a zároveň pridáva správne množstvo spodkov a čistoty, ktoré preferujú dnešní metaloví hráči.",
    "It allows better and multidirectional high fret access.":
        "Umožňuje lepší a viacsmerný prístup k vysokým pražcom.",
}
SK_PHRASES = {_norm(k): v for k, v in _SK_NARRATIVE.items()}


def sk_text(s, lang):
    """Translate narrative copy to Slovak via the phrase map; English fallback."""
    if lang != "sk" or not s:
        return s
    return SK_PHRASES.get(_norm(s), s)


def li(label, value, lang="en"):
    v = clean(value)
    if not v:
        return ""
    if lang == "sk":
        label = SK_SPEC_LABELS.get(label, label)
        v = SK_SPEC_VALUES.get(v, v)
    return f"<li>{html.escape(label)} - {html.escape(v)}</li>"


def build_html(rec, img_urls=None, lang="en"):
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
    intro_html = "".join(f"<p>{html.escape(sk_text(p, lang))}</p>" for p in intro_paras)

    country = clean(rec.get("Country of origin"))
    if country and lang == "sk":
        _c = SK_SPEC_VALUES.get(country, country)
        made_in = "Vyrobené v " + SK_COUNTRY_LOC.get(_c, _c)
    elif country:
        made_in = "Made in " + country
    else:
        made_in = ""
    subtitle = " · ".join([x for x in (grade, category, made_in) if x])

    # ---- three highlight columns (first three product features) ----
    cols = []
    for t, b in features[:3]:
        cols.append(
            '<div class="feature-item">'
            '<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" '
            'fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" '
            'stroke-linejoin="round"><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 '
            '2 12s4.477 10 10 10z"></path><path d="m9 12 2 2 4-4"></path></svg>'
            f'<h4>{html.escape(sk_text(t, lang))}</h4>'
            f'<div class="prose max-w-none">{html.escape(sk_text(b, lang))}</div></div>'
        )
    cols_html = "\n".join(cols)

    # ---- full feature list with explanations ----
    feat_items = "\n".join(
        f"<li><strong>{html.escape(sk_text(t, lang))}</strong>"
        + (f" — {html.escape(sk_text(b, lang))}" if b else "") + "</li>"
        for t, b in features
    )
    special_items = "\n".join(
        f"<li><strong>{html.escape(sk_text(t, lang))}</strong>"
        + (f" — {html.escape(sk_text(b, lang))}" if b else "") + "</li>"
        for t, b in special
    )

    # ---- specification groups ----
    thk1, thk12 = clean(rec.get('Neck thickness (1st fret, mm)')), clean(rec.get('Neck thickness (12th fret, mm)'))
    _at1 = "mm (1. pražec)" if lang == "sk" else "mm @1st"
    _at12 = "mm (12. pražec)" if lang == "sk" else "mm @12th"
    neck_thk = " / ".join(x for x in [
        f"{thk1} {_at1}" if thk1 else "",
        f"{thk12} {_at12}" if thk12 else "",
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
    _top, _bodym = clean(rec.get("Body Top material (For Solid)")), clean(rec.get("Body Material (For Solid)"))
    if lang == "sk":
        body_wood = " / ".join(x for x in [
            f'vrchná doska {_top}' if _top else "",
            f'telo {SK_SPEC_VALUES.get(_bodym, _bodym)}' if _bodym else "",
        ] if x)
    else:
        body_wood = " / ".join(x for x in [
            f'{_top} top' if _top else "",
            f'{_bodym} body' if _bodym else "",
        ] if x)

    specs_1 = "\n".join(x for x in [
        li("Body", body_wood, lang),
        li("Neck type", rec.get("Neck Type"), lang),
        li("Neck material", rec.get("Neck Material"), lang),
        li("Neck joint", rec.get("Neck Joint"), lang),
        li("Neck finish", rec.get("Neck finish"), lang),
        li("Neck thickness", neck_thk, lang),
        li("Scale", scale, lang),
        li("Fretboard", rec.get("Fretboard"), lang),
        li("Fretboard radius", fb_radius, lang),
        li("Frets", (clean(rec.get("Number of fret")) + ", " if clean(rec.get("Number of fret")) else "") + clean(rec.get("Fret Type")), lang),
        li("Fret edge treatment", rec.get("Fret edge treatment"), lang),
        li("Inlay", rec.get("Inlay"), lang),
        li("Nut width", nut_w, lang),
        li("Number of strings", rec.get("Number of Strings"), lang),
        li("Body finish", rec.get("Body finish"), lang),
        li("Country of origin", rec.get("Country of origin"), lang),
    ] if x)

    specs_2 = "\n".join(x for x in [
        li("Bridge", rec.get("Bridge"), lang),
        li("Nut", rec.get("Nut"), lang),
        li("Machine heads", rec.get("Machine Head"), lang),
        li("Hardware color", rec.get("Hardware color"), lang),
        li("Neck pickup", rec.get("Neck Pickup"), lang),
        li("Bridge pickup", rec.get("Bridge Pickup"), lang),
        li("Electronics", rec.get("Active or Passive"), lang),
        li("Controls", rec.get("Controls, Pickup selector"), lang),
        li("Switching", rec.get("Other Switches"), lang),
        li("String spacing", (clean(rec.get("String spacing (mm)")) + "mm") if clean(rec.get("String spacing (mm)")) else "", lang),
        li("Side dot inlay", rec.get("Side Dot Inlay"), lang),
        li("Strap lock", rec.get("Strap Lock"), lang),
        li("Strings", rec.get("Special Strings") or rec.get("String Gauges (from top to bottom)"), lang),
        li("String gauges", rec.get("String Gauges (from top to bottom)"), lang),
        li("Tuning", rec.get("Tuning (from top to bottom)"), lang),
        li("Case / bag", rec.get("Included case/bag"), lang),
        li("Also included", rec.get("Other item(s) included"), lang),
    ] if x)

    H = (lambda h: SK_HEADINGS.get(h, h)) if lang == "sk" else (lambda h: h)

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
        parts.append(f'<div class="desc-text"><h3>{html.escape(H("Features"))}</h3><div class="prose max-w-none"><ul>\n{feat_items}\n</ul></div></div>')
        parts.append('</section>')

    if special_items:
        parts.append('<section class="desc-section image-layout-right">')
        parts.append(f'<div class="desc-image fit-contain" style="height:450px;max-height:450px;">{img3_tag}</div>')
        parts.append(f'<div class="desc-text"><h3>{html.escape(H("Special Features"))}</h3><div class="prose max-w-none"><ul>\n{special_items}\n</ul></div></div>')
        parts.append('</section>')

    if specs_1:
        parts.append('<section class="desc-section image-layout-left">')
        parts.append('<div class="desc-image fit-contain" style="height:450px;max-height:450px;"></div>')
        parts.append(f'<div class="desc-text"><h3>{html.escape(H("Specifications"))}</h3><div class="prose max-w-none"><ul>\n{specs_1}\n</ul></div></div>')
        parts.append('</section>')

    if specs_2:
        parts.append('<section class="desc-section image-layout-right">')
        parts.append('<div class="desc-image fit-contain" style="height:450px;max-height:450px;"></div>')
        parts.append(f'<div class="desc-text"><h3>{html.escape(H("Electronics & Hardware"))}</h3><div class="prose max-w-none"><ul>\n{specs_2}\n</ul></div></div>')
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

    desc = clean(rec.get("Description"))
    has_case = bool(desc and "CASE" in desc.upper())

    def _name(case_label):
        bits = ["Ibanez", model]
        if grade:
            bits.append(grade)
        if color_name:
            bits.append(color_name)
        if has_case:
            bits.append(case_label)
        return " ".join(bits)

    name = _name("(with Case)")
    name_sk = _name("(s puzdrom)")

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

    # ---- Slovak meta (structured templates; ≤60 title / ≤160 description) ----
    country = clean(rec.get("Country of origin"))
    country_sk = SK_SPEC_VALUES.get(country, country)
    country_loc = SK_COUNTRY_LOC.get(country_sk, country_sk)
    feats, _ = parse_feature_blocks(rec.get("Copy") or rec.get("Product_Features"))
    feat_sk = [sk_text(t, "sk") for t, _ in feats[:3]]
    _grade = (grade + " ") if grade else ""
    meta_title_sk = f"Ibanez {model} {_grade}elektrická gitara, {color_name}".strip()[:60]
    # Assemble ≤160 chars without cutting a word: head + as many features as fit + tail.
    head = (f"Ibanez {model} {grade}".strip()) + (f", {color_name}" if color_name else "")
    tail = (f" Vyrobené v {country_loc}." if country_sk else "") + " Predobjednávka."
    chosen = []
    for f in feat_sk:
        if len(head + ": " + ", ".join(chosen + [f]) + "." + tail) <= 160:
            chosen.append(f)
        else:
            break
    meta_desc_sk = (head + ": " + ", ".join(chosen) + "." + tail) if chosen else (head + "." + tail)
    meta_desc_sk = meta_desc_sk.strip()[:160]
    meta_keyword_sk = ", ".join([x for x in [
        f"Ibanez {model}", (f"Ibanez {grade}" if grade else ""), f"{model} {color_name}".strip(),
        "Ibanez elektrická gitara", (f"gitara {grade}" if grade else "")] if x])
    tag_sk = ", ".join([x for x in ["Ibanez", model, grade, color_name, "elektrická gitara"] if x])

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
        "HTML_Description": build_html(rec, servable, lang="en"),
        # Slovak (language_id=2) — consumed by create_products.js
        "Name_sk": name_sk,
        "MetaTitle_sk": meta_title_sk,
        "MetaDescription_sk": meta_desc_sk,
        "MetaKeyword_sk": meta_keyword_sk,
        "Tag_sk": tag_sk,
        "HTML_Description_sk": build_html(rec, servable, lang="sk"),
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
                  "Quantity", "Image_1", "Image_2", "Image_3", "HTML_Description",
                  "Name_sk", "MetaTitle_sk", "MetaDescription_sk", "MetaKeyword_sk",
                  "Tag_sk", "HTML_Description_sk"]
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
