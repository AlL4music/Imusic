import time
import re
import pandas as pd
import requests
from bs4 import BeautifulSoup

# --- NASTAVENIA ---
SITEMAP_URL = 'https://imusicdata.sk/site-map-products-sk.xml'
VYSTUPNY_SUBOR = 'imusicdata_sklad.csv'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}
PAUZA_MEDZI_POZIADAVKAMI = 0.2

def get_all_product_urls(sitemap_url):
    print(f"Načítavam sitemapu z: {sitemap_url}")
    try:
        response = requests.get(sitemap_url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'lxml-xml')
        
        # Načítame všetky lokácie zo sitemapy
        product_urls = [loc.text for loc in soup.find_all('loc') if loc.text]
        
        print(f"Nájdených {len(product_urls)} produktových URL adries.")
        return product_urls
    except Exception as e:
        print(f"!!! CHYBA sitemapy: {e}")
        return None

def scrape_product_data(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            return None 

        soup = BeautifulSoup(response.content, 'html.parser')

        # 1. Nájdi Názov - podľa zadania: h1 class="product-name"
        nazov_element = soup.find('h1', class_='product-name')
        nazov_produktu = nazov_element.get_text(strip=True) if nazov_element else "N/A"

        # 2. Nájdi Kód produktu (SKU) - podľa zadania: strong
        # Hľadáme strong tag, ktorý pravdepodobne obsahuje kód
        sku_element = soup.find('strong', string=re.compile(r'.+'))
        kod_produktu = sku_element.get_text(strip=True) if sku_element else None

        # 3. Nájdi Stav Skladu - podľa zadania: span class="sign in-stock"
        skladom_hodnota = 0 
        stock_span = soup.find('span', class_='sign in-stock')
        if stock_span:
            stock_text = stock_span.get_text(strip=True).lower() # napr. "skladom 5 ks"
            # Vytiahneme číslo
            match = re.search(r'(\d+)', stock_text)
            if match:
                skladom_hodnota = int(match.group(1))
            elif "skladom" in stock_text:
                skladom_hodnota = 1
        
        if kod_produktu:
            return {
                'SKU': kod_produktu,
                'Nazov': nazov_produktu,
                'Pocet_ks': skladom_hodnota,
                'URL': url
            }
    except:
        return None

if __name__ == "__main__":
    urls = get_all_product_urls(SITEMAP_URL)
    if urls:
        vysledky = []
        for i, url in enumerate(urls):
            if (i + 1) % 50 == 0:
                 print(f"Spracovaných {i + 1}/{len(urls)}...")
            data = scrape_product_data(url)
            if data:
                vysledky.append(data)
            time.sleep(PAUZA_MEDZI_POZIADAVKAMI) 

        if vysledky:
            pd.DataFrame(vysledky).to_csv(VYSTUPNY_SUBOR, index=False, encoding='utf-8-sig', sep=';')
            print(f"HOTOVO! Uložené do {VYSTUPNY_SUBOR}")
