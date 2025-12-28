import time
import re
import pandas as pd
import requests
from bs4 import BeautifulSoup

# --- NASTAVENIA ---
SITEMAP_URL = 'https://www.rockster.cz/sitemap-product-1.xml'
VYSTUPNY_SUBOR = 'rockster_sklad.csv'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}
PAUZA_MEDZI_POZIADAVKAMI = 0.2
TESTOVACI_POCET = 0 

def get_all_product_urls(sitemap_url):
    print(f"Načítavam sitemapu z: {sitemap_url}")
    product_urls = []
    try:
        response = requests.get(sitemap_url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'lxml-xml')
        
        if not soup.find('urlset'):
            return None

        for url_tag in soup.find_all('url'):
            loc_tag = url_tag.find('loc') 
            if loc_tag:
                product_urls.append(loc_tag.text)
        
        print(f"Celkovo nájdených {len(product_urls)} URL adries.")
        return product_urls
    except Exception as e:
        print(f"!!! CHYBA sitemapy: {e}")
        return None

def scrape_product_data(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            return None 

        soup = BeautifulSoup(response.content, 'html.parser')
        nazov_element = soup.find('h1')
        nazov_produktu = nazov_element.get_text(strip=True) if nazov_element else "Názov nenájdený"

        kod_produktu = None
        sku_span = soup.find('span', class_='js_kod')
        if sku_span:
            kod_produktu = sku_span.get_text(strip=True)

        cena_finalna = "0"
        price_span = soup.find('span', class_='price')
        if price_span:
            cena_text = price_span.get_text(strip=True)
            cena_finalna = cena_text.replace('€', '').replace('\xa0', '').replace(' ', '').strip()

        skladom_hodnota = 0 
        stock_span = soup.find('span', class_='status js_dostupnost')
        if stock_span:
            stock_text = stock_span.get_text(strip=True).lower()
            if 'skladem' in stock_text:
                match = re.search(r'\(>?(\d+)\s*ks\)', stock_text)
                skladom_hodnota = int(match.group(1)) if match else 1 
        
        if kod_produktu:
            return {
                'SKU': kod_produktu,
                'Nazov': nazov_produktu,
                'Cena': cena_finalna,
                'Pocet_ks': skladom_hodnota,
                'URL': url
            }
    except:
        return None

if __name__ == "__main__":
    product_urls = get_all_product_urls(SITEMAP_URL)
    if product_urls:
        urls_na_spracovanie = product_urls
        vysledky = []
        for i, url in enumerate(urls_na_spracovanie):
            if (i + 1) % 50 == 0:
                 print(f"Spracovaných {i + 1}/{len(urls_na_spracovanie)}...")
            data = scrape_product_data(url)
            if data:
                vysledky.append(data)
            time.sleep(PAUZA_MEDZI_POZIADAVKAMI) 

        if vysledky:
            vysledky_df = pd.DataFrame(vysledky)
            vysledky_df.to_csv(VYSTUPNY_SUBOR, index=False, encoding='utf-8-sig', sep=';')
            print(f"HOTOVO! Uložené do {VYSTUPNY_SUBOR}")
