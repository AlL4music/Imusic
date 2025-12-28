import time
import re
import pandas as pd
import requests
from bs4 import BeautifulSoup

# --- NASTAVENIA ---
SITEMAP_URL = 'https://www.3dmx.cz/sitemap/sitemap_cs.xml'
VYSTUPNY_SUBOR = '3dmx_sklad.csv'
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
        
        # Odfiltrujeme len tie, ktoré vyzerajú ako produkty (väčšinou neobsahujú /kategorie/ alebo /znacka/)
        filtered_urls = [url for url in product_urls if '/c/' not in url and '/vyr/' not in url]
        
        print(f"Nájdených {len(filtered_urls)} produktových URL adries.")
        return filtered_urls
    except Exception as e:
        print(f"!!! CHYBA sitemapy: {e}")
        return None

def scrape_product_data(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            return None 

        soup = BeautifulSoup(response.content, 'html.parser')

        # 1. Nájdi Kód produktu (SKU) - podľa tvojho zadania: td class="td_katalog_detail_polozka"
        sku_td = soup.find('td', class_='td_katalog_detail_polozka')
        kod_produktu = sku_td.get_text(strip=True) if sku_td else None

        # 2. Nájdi Názov
        nazov_element = soup.find('h1')
        nazov_produktu = nazov_element.get_text(strip=True) if nazov_element else "N/A"

        # 3. Nájdi Stav Skladu - podľa tvojho zadania: span class="skladem"
        skladom_hodnota = 0 
        stock_span = soup.find('span', class_='skladem')
        if stock_span:
            stock_text = stock_span.get_text(strip=True).lower() # napr. "2ks"
            # Vytiahneme len čísla z textu "2ks"
            match = re.search(r'(\d+)', stock_text)
            if match:
                skladom_hodnota = int(match.group(1))
            elif "skladem" in stock_text or "ano" in stock_text:
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
