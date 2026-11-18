"""
Meinl B2B stock (b2b.meinl.de) -> stock/{Meinl,Tama,Ibanez,Ortega,Nino}.csv

Prihlasovacie udaje sa citaju z prostredia (MEINL_B2B_USER / MEINL_B2B_PASS),
nikdy nie su v repozitari.

Portal je ASP.NET aplikacia s nahodnymi nazvami poli vo formulari, preto sa
pouziva skutocny prehliadac (Playwright) a polia sa hladaju podla toho, co je
na stranke viditelne.

Rezimy:
  python meinl_b2b.py --discover   # len popise VEREJNU prihlasovaciu stranku
"""

import argparse
import sys

from playwright.sync_api import sync_playwright

BASE_URL = "https://b2b.meinl.de/"

DESCRIBE_INPUTS_JS = """
() => Array.from(document.querySelectorAll('form input, form button, form select')).map(el => {
  const r = el.getBoundingClientRect();
  const cs = getComputedStyle(el);
  const lab = el.labels && el.labels.length ? el.labels[0].innerText.trim() : null;
  return {
    tag: el.tagName.toLowerCase(),
    type: el.type || null,
    visible: r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none' && cs.opacity !== '0',
    box: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)],
    placeholder: el.getAttribute('placeholder'),
    autocomplete: el.getAttribute('autocomplete'),
    label: lab,
    text: (el.innerText || el.value || '').trim().slice(0, 40),
    cls: el.className || null,
    tabindex: el.getAttribute('tabindex'),
  };
})
"""


def discover() -> int:
    """Popise verejnu prihlasovaciu stranku tak, ako ju vidi prehliadac. Ziadne prihlasenie."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(locale="en-US")
        page.goto(BASE_URL, wait_until="networkidle", timeout=60000)
        print(f"url: {page.url}")
        print(f"title: {page.title()}")
        for i, item in enumerate(page.evaluate(DESCRIBE_INPUTS_JS)):
            print(f"[{i}] {item}")
        browser.close()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--discover", action="store_true")
    args = ap.parse_args()
    if args.discover:
        return discover()
    print("Zatial je hotovy len rezim --discover.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
