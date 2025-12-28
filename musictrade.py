import time
import re
import json
import pandas as pd
import requests
from bs4 import BeautifulSoup

# --- NASTAVENIA ---
SITEMAP_URL = 'https://www.musictrade.cz/sitemap.xml'
VYSTUPNY_SUBOR = 'musictrade_sklad.csv'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}
PAUZA_MEDZI_POZIADAVKAMI = 0.002

def get_all_product_urls(sitemap_url):
    print(f"Načítavam sitemapu z: {sitemap_url}")
    product_urls = []
    try:
        response = requests.get(sitemap_url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'lxml-xml')
        
        all_urls = [loc.text for loc in soup.find_all('loc') if loc.text]
        print(f"Nájdených {len(all_urls)} URL. Filtrujem produkty...")

        for url in all_urls:
            if '/znacka/' not in url and '/kategorie/' not in url:
                product_urls.append(url)
        
        return product_urls
    except Exception as e:
        print(f"!!! CHYBA sitemapy: {e}")
        return None

def scrape_product_data(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200: return None

        soup = BeautifulSoup(response.content, 'html.parser')
        scripts = soup.find_all('script')
        data_script = next((s.string for s in scripts if s.string and 'dataLayer.push' in s.string and '"product":' in s.string), None)

        if not data_script: return None

        match = re.search(r'"product":\s*({.*?"priceWithVat":.*?})\s*,', data_script, re.DOTALL)
        if not match: return None
        
        product_data = json.loads(match.group(1).replace(r'\/', '/'))
        
        skladom_hodnota = 0
        if product_data.get('codes'):
            quantity_str = product_data['codes'][0].get('quantity')
            if quantity_str:
                quantity_clean = quantity_str.replace('>', '').strip()
                try:
                    skladom_hodnota = int(quantity_clean)
                except ValueError:
                    skladom_hodnota = 1 
        
        return {
            'SKU': product_data.get('code'),
            'Nazov': product_data.get('name'),
            'Pocet_ks': skladom_hodnota,
            'URL': url
        }
    except:
        return None

if __name__ == "__main__":
    product_urls = get_all_product_urls(SITEMAP_URL)
    if product_urls:
        # Ponechávame tvoj START_INDEX = 400
        START_INDEX = 400
        urls_na_spracovanie = product_urls[START_INDEX:] if len(product_urls) > START_INDEX else []
        
        vysledky = []
        for i, url in enumerate(urls_na_spracovanie):
            if (i + 1) % 50 == 0:
                print(f"Spracované [{i + 1}/{len(urls_na_spracovanie)}]")
            data = scrape_product_data(url)
            if data:
                vysledky.append(data)
            time.sleep(PAUZA_MEDZI_POZIADAVKAMI)

        if vysledky:
            pd.DataFrame(vysledky).to_csv(VYSTUPNY_SUBOR, index=False, encoding='utf-8-sig', sep=';')
            print(f"HOTOVO! Uložené do {VYSTUPNY_SUBOR}")
