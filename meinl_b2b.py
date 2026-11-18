"""
Meinl B2B stock (b2b.meinl.de) -> stock/{Meinl,Tama,Ibanez,Ortega,Nino}.csv

Prihlasovacie udaje sa citaju z prostredia (MEINL_B2B_USER / MEINL_B2B_PASS),
nikdy nie su v repozitari.

Rezimy:
  python meinl_b2b.py --discover   # len zisti, ako vyzera verejna prihlasovacia stranka
"""

import argparse
import sys
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://b2b.meinl.de/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en,de;q=0.9,sk;q=0.8",
}


def discover() -> int:
    """Vypise strukturu VEREJNEJ prihlasovacej stranky (ziadne prihlasenie, ziadne data)."""
    s = requests.Session()
    s.headers.update(HEADERS)
    r = s.get(BASE_URL, timeout=30)
    print(f"status={r.status_code} final_url={r.url}")
    for h in r.history:
        print(f"  redirect {h.status_code} -> {h.headers.get('Location')}")
    for k in ("Server", "X-Powered-By", "Content-Type", "Set-Cookie"):
        v = r.headers.get(k)
        if v:
            # pri cookies staci nazov, nie hodnota
            if k == "Set-Cookie":
                v = ", ".join(c.split("=")[0].strip() for c in v.split(","))
            print(f"header {k}: {v}")
    soup = BeautifulSoup(r.text, "lxml")
    print(f"title: {soup.title.string.strip() if soup.title and soup.title.string else None}")
    gen = soup.find("meta", attrs={"name": "generator"})
    print(f"generator: {gen.get('content') if gen else None}")
    print(f"html bytes: {len(r.text)}")
    for i, f in enumerate(soup.find_all("form")):
        print(f"form[{i}] method={f.get('method')} action={urljoin(r.url, f.get('action') or '')} id={f.get('id')}")
        for inp in f.find_all(["input", "select", "button"]):
            print(f"    {inp.name} name={inp.get('name')} type={inp.get('type')} id={inp.get('id')}")
    scripts = [urljoin(r.url, sc["src"]) for sc in soup.find_all("script", src=True)]
    print(f"scripts ({len(scripts)}):")
    for sc in scripts[:25]:
        print(f"    {sc}")
    links = sorted({urljoin(r.url, a["href"]) for a in soup.find_all("a", href=True)})
    print(f"links ({len(links)}):")
    for l in links[:40]:
        print(f"    {l}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--discover", action="store_true")
    args = p.parse_args()
    if args.discover:
        return discover()
    print("Zatial je hotovy len rezim --discover.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
