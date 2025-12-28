import time
import re
import pandas as pd
import requests
from bs4 import BeautifulSoup

# --- NASTAVENIA ---
SITEMAP_URL = 'https://www.eprodance.cz/sitemap.xml'
VYSTUPNY_SUBOR = 'eprodance_sklad.csv'
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
        
        # Načítame všetky URL
        all_urls = [loc.text for loc in soup.find_all('loc') if loc.text]
        
        # Filtrujeme produkty (vylúčime kategórie, značky, články)
        # Na eprodance.cz produkty zvyčajne nemajú v ceste /clanky/, /blog/ atď.
        product_urls = [url for url in all_urls if '/p/' in url or '-' in url.split('/')[-1]]
        
        # Ak je sitemapa veľmi veľká, môžeme odfiltrovať tie, ktoré neobsahujú produktový vzor
        print(f"Nájdených {len(product_urls)} potenciálnych produktových URL adries.")
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

        # 1. Názov - podľa zadania: h1
        nazov_element = soup.find('h1')
        nazov_produktu = nazov_element.get_text(strip=True) if nazov_element else "N/A"

        # 2. Kód produktu (SKU) - podľa zadania: span (často býva v kontajneri s kódom)
        # Hľadáme span, ktorý obsahuje len čísla alebo je v blízkosti názvu
        sku_element = soup.find('span', string=re.compile(r'^\d+$'))
        if not sku_element:
             # Skúsime nájsť span podľa kontextu, ak sa kód nachádza v špecifickom div-e
             sku_container = soup.find('div', class_='product-code') or soup.find('span', class_='code')
             sku_element = sku_container.find('span') if sku_container else None
        
        kod_produktu = sku_element.get_text(strip=True) if sku_element else None

        # 3. Stav Skladu - podľa zadania: span class="availability-amount"
        skladom_hodnota = 0 
        stock_span = soup.find('span', class_='availability-amount')
        if stock_span:
            stock_text = stock_span.get_text(strip=True) # napr. "(11 ks)"
            # Vytiahneme číslo pomocou regexu
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

if __name__ == "__main__":
    urls = get_all_product_urls(SITEMAP_URL)
    if urls:
        vysledky = []
        # Pre začiatok spracujeme všetky, v prípade potreby sa dá START_INDEX posunúť
        for i, url in enumerate(urls):
            if (i + 1) % 50 == 0:
                 print(f"Spracované {i + 1}/{len(urls)}...")
            data = scrape_product_data(url)
            if data:
                vysledky.append(data)
            time.sleep(PAUZA_MEDZI_POZIADAVKAMI) 

        if vysledky:
            pd.DataFrame(vysledky).to_csv(VYSTUPNY_SUBOR, index=False, encoding='utf-8-sig', sep=';')
            print(f"HOTOVO! Uložené do {VYSTUPNY_SUBOR}")
