import time
import re
import pandas as pd
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings

warnings.filterwarnings("ignore", category=UserWarning, module='bs4')

# --- NASTAVENIA ---
SITEMAP_URL = 'https://www.eprodance.cz/sitemap.xml'
VYSTUPNY_SUBOR = 'eprodance_sklad.csv'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

MAX_WORKERS = 10 
TIMEOUT = 20

session = requests.Session()
session.headers.update(HEADERS)

def get_all_product_urls(sitemap_url):
    print(f"Načítavam sitemapu: {sitemap_url}")
    try:
        response = session.get(sitemap_url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'lxml-xml')
        
        product_urls = []
        for url_tag in soup.find_all('url'):
            # Precision: hľadáme len <loc> priamo pod <url>, ignorujeme <image:loc>
            loc = url_tag.find('loc', recursive=False)
            if loc:
                url_text = loc.text
                # Vyradíme balast
                blacklist = ['/znacka/', '/clanky/', '/blog/', '/vyrobce/', '/kontakt', '/o-nas', '/kosik', '/zakaznik']
                if not any(b in url_text for b in blacklist):
                    product_urls.append(url_text)
        
        return list(set(product_urls))
    except Exception as e:
        print(f"!!! CHYBA sitemapy: {e}")
        return []

def scrape_product_data(url):
    try:
        response = session.get(url, timeout=TIMEOUT)
        if response.status_code != 200:
            return None 

        html_text = response.content.decode('utf-8', errors='ignore')
        soup = BeautifulSoup(html_text, 'html.parser')

        # 1. Názov (H1)
        nazov_element = soup.find('h1')
        if not nazov_element:
            return None
        nazov_produktu = nazov_element.get_text(strip=True)

        # 2. Kód produktu (SKU) - Shoptet FIX
        # Skúšame viacero možností, kde môže byť kód
        sku_element = (
            soup.find('span', class_='code') or 
            soup.find('span', itemprop='sku') or
            soup.find('meta', itemprop='sku')
        )
        
        kod_produktu = None
        if sku_element:
            # Ak je to meta tag, vezmeme 'content', inak text
            kod_produktu = sku_element.get('content') if sku_element.name == 'meta' else sku_element.get_text(strip=True)

        # 3. Stav Skladu - Shoptet FIX
        skladom_hodnota = 0 
        # Hľadáme triedu 'availability-amount' alebo 'stock'
        stock_span = soup.find('span', class_='availability-amount') or soup.find('span', class_='stock-amount')
        
        if stock_span:
            stock_text = stock_span.get_text(strip=True)
            # Vytiahneme len čísla (napr. z "(15 ks)" dostaneme 15)
            match = re.search(r'(\d+)', stock_text)
            if match:
                skladom_hodnota = int(match.group(1))
        
        if kod_produktu:
            return {
                'SKU': kod_produktu,
                'Nazov': nazov_produktu,
                'Pocet_ks': skladom_hodnota,
                'URL': url
            }
    except:
        return None
    return None

if __name__ == "__main__":
    # DEBUG TEST pre vašu URL
    test_url = "https://www.eprodance.cz/b-c-speakers-8ndl51-recone-kit-16-ohm/"
    print(f"Spúšťam test pre URL: {test_url}")
    test_data = scrape_product_data(test_url)
    if test_data:
        print(f"TEST ÚSPEŠNÝ: {test_data}")
    else:
        print("TEST ZLYHAL: Produktové dáta sa nepodarilo vybrať.")

    # POKRAČOVANIE V CELOM SCRAPE
    urls = get_all_product_urls(SITEMAP_URL)
    if urls:
        vysledky = []
        print(f"Spracovávam {len(urls)} adries...")
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_url = {executor.submit(scrape_product_data, url): url for url in urls}
            for i, future in enumerate(as_completed(future_to_url)):
                data = future.result()
                if data:
                    vysledky.append(data)
                if (i + 1) % 100 == 0:
                    print(f"Progress: {i + 1}/{len(urls)} | Získané produkty: {len(vysledky)}")

        df = pd.DataFrame(vysledky)
        df.to_csv(VYSTUPNY_SUBOR, index=False, encoding='utf-8-sig', sep=';')
        print(f"HOTOVO! Uložených {len(df)} produktov.")
