"""
Meinl B2B stock (b2b.meinl.de) -> stock/{Meinl,Tama,Ibanez,Ortega,Nino}.csv

Prihlasovacie udaje sa citaju z prostredia (MEINL_B2B_USER / MEINL_B2B_PASS),
nikdy nie su v repozitari.

Portal je ASP.NET aplikacia. Prihlasovaci formular ma nahodne nazvy poli a
navnady umiestnene mimo obrazovky, preto sa pouziva skutocny prehliadac
(Playwright) a vyplnaju sa len polia autocomplete=username / current-password.

Rezimy:
  python meinl_b2b.py --explore   # prihlasi sa a vypise LEN strukturu menu a
                                  # odkazy na exporty (ziadne ceny, ziadne data)
"""

import argparse
import os
import re
import sys
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

BASE_URL = "https://b2b.meinl.de/"
USER_SEL = 'input[autocomplete="username"]'
PASS_SEL = 'input[autocomplete="current-password"]'
EXPORT_RE = re.compile(
    r"export|download|csv|excel|xls|stock|availab|verf(ü|ue)gbar|lager|bestand|preisliste|price ?list|artikel|item|catalog|katalog",
    re.I,
)


def login(page) -> bool:
    """Jeden pokus o prihlasenie. Vrati True, ak sme sa dostali za prihlasovaciu stranku."""
    user = os.environ.get("MEINL_B2B_USER", "").strip()
    password = os.environ.get("MEINL_B2B_PASS", "")
    if not user or not password:
        print("CHYBA_SECRETS: MEINL_B2B_USER / MEINL_B2B_PASS nie su nastavene.")
        return False
    page.goto(BASE_URL, wait_until="networkidle", timeout=60000)
    page.fill(USER_SEL, user)
    page.fill(PASS_SEL, password)
    page.press(PASS_SEL, "Enter")
    page.wait_for_load_state("networkidle", timeout=60000)
    ok = "/Account/Login" not in page.url
    print(f"login_ok={ok} path={urlsplit(page.url).path}")
    return ok


def explore() -> int:
    """Po prihlaseni vypise len navigaciu: text odkazu + cesta. Nic z tabuliek, ziadne ceny."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(locale="en-US")
        if not login(page):
            browser.close()
            return 0 if not os.environ.get("MEINL_B2B_USER") else 1
        print(f"title: {page.title()}")
        items = page.evaluate(
            """() => Array.from(document.querySelectorAll('a[href], button, input[type=submit]')).map(el => ({
                 tag: el.tagName.toLowerCase(),
                 text: (el.innerText || el.value || el.getAttribute('title') || '').trim().replace(/\\s+/g, ' ').slice(0, 60),
                 href: el.getAttribute('href'),
                 inTable: !!el.closest('table, tbody, .grid, .k-grid'),
               }))"""
        )
        seen = set()
        nav, exports = [], []
        for it in items:
            if it["inTable"]:
                continue
            href = it["href"] or ""
            path = urlsplit(href).path if href and not href.startswith(("mailto:", "tel:", "javascript:")) else ""
            key = (it["text"], path)
            if key in seen or (not it["text"] and not path):
                continue
            seen.add(key)
            (exports if EXPORT_RE.search(it["text"] + " " + href) else nav).append((it["tag"], it["text"], path))
        print(f"export-like ({len(exports)}):")
        for t in exports[:80]:
            print(f"    {t}")
        print(f"other navigation ({len(nav)}):")
        for t in nav[:80]:
            print(f"    {t}")
        browser.close()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--explore", action="store_true")
    args = ap.parse_args()
    if args.explore:
        return explore()
    print("Zatial je hotovy len rezim --explore.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
