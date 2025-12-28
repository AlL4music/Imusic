import time
import re
import pandas as pd
import requests
from bs4 import BeautifulSoup

# --- NASTAVENIA ---
SITEMAP_URL = 'https://www.music-park.sk/sitemap.xml'
VYSTUPNY_SUBOR = 'musicpark_sklad.csv'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}
PAUZA_MEDZI_POZIADAVKAMI = 0.2

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
            if '/produkt/' in url:
                product_urls.append(url)
        
        print(f"Celkovo nájdených {len(product_urls)} produktov na kontrolu.")
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
        nazov_element = soup.find('h1')
        nazov_produktu = nazov_element.get_text(strip=True) if nazov_element else "N/A"

        kod_produktu = None
        sku_div = soup.find('div', string=re.compile(r'Obj\. kód:'))
        if sku_div:
            kod_produktu = sku_div.get_text(strip=True).split(':')[-1].strip().replace('\xa0', '')

        skladom_hodnota = 0
        stock_span = soup.find('span', class_='dostupnost')
        if stock_span:
            stock_text = stock_span.get_text(strip=True).lower()
            if 'skladom' in stock_text:
                match = re.search(r'skladom (\d+)', stock_text)
                skladom_hodnota = int(match.group(1)) if match else 1
        
        if kod_produktu:
            return {'SKU': kod_produktu, 'Nazov': nazov_produktu, 'Pocet_ks': skladom_hodnota, 'URL': url}
    except:
        return None

if __name__ == "__main__":
    product_urls = get_all_product_urls(SITEMAP_URL)
    if product_urls:
        vysledky = []
        for i, url in enumerate(product_urls):
            if (i + 1) % 50 == 0:
                print(f"Spracované [{i + 1}/{len(product_urls)}]")
            data = scrape_product_data(url)
            if data:
                vysledky.append(data)
            time.sleep(PAUZA_MEDZI_POZIADAVKAMI)

        if vysledky:
            pd.DataFrame(vysledky).to_csv(VYSTUPNY_SUBOR, index=False, encoding='utf-8-sig', sep=';')
            print(f"HOTOVO! Uložené do {VYSTUPNY_SUBOR}")
