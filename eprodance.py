import time
import re
import pandas as pd
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings

# Umlčíme varovania BeautifulSoup o kódovaní
warnings.filterwarnings("ignore", category=UserWarning, module='bs4')

# --- NASTAVENIA ---
SITEMAP_URL = 'https://www.eprodance.cz/sitemap.xml'
VYSTUPNY_SUBOR = 'eprodance_sklad.csv'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

MAX_WORKERS = 15 
TIMEOUT = 15

session = requests.Session()
session.headers.update(HEADERS)

def get_all_product_urls(sitemap_url):
    print(f"Načítavam sitemapu: {sitemap_url}")
    try:
        response = session.get(sitemap_url, timeout=30)
        response.raise_for_status()
        
        # Použijeme lxml-xml na čisté spracovanie XML tagov
        soup = BeautifulSoup(response.content, 'lxml-xml')
        
        # --- FILTROVANIE ODKAZOV ---
        product_urls = []
        # Hľadáme všetky <url> tagy
        for url_tag in soup.find_all('url'):
            # Zoberieme LEN <loc> tag, ktorý je priamym potomkom <url>
            # Týmto ignorujeme <image:loc>, ktorý je vnorený hlbšie
            loc = url_tag.find('loc', recursive=False)
            
            if loc:
                url_text = loc.text
                
                # Vyradíme balast: značky, blogy, kategórie a systémové stránky
                blacklist = ['/znacka/', '/clanky/', '/blog/', '/vyrobce/', '/kontakt', '/o-nas', '/kosik', '/zakaznik']
                if not any(b in url_text for b in blacklist):
                    product_urls.append(url_text)
        
        product_urls = list(set(product_urls)) # Odstránenie duplicít
        print(f"Nájdených {len(product_urls)} čistých produktových adries (obrázky a značky odfiltrované).")
        return product_urls
    except Exception as e:
        print(f"!!! CHYBA sitemapy: {e}")
        return []

def scrape_product_data(url):
    try:
        response = session.get(url, timeout=TIMEOUT)
        if response.status_code != 200:
            return None 

        # Dekódovanie textu s ignorovaním chybných znakov
        html_text = response.content.decode('utf-8', errors='ignore')
        soup = BeautifulSoup(html_text, 'html.parser')

        # 1. Kontrola, či ide o produkt (Shoptet weby majú často 'type-product')
        # Ak nenájdeme H1, stránku preskočíme
        nazov_element = soup.find('h1')
        if not nazov_element:
            return None
        nazov_produktu = nazov_element.get_text(strip=True)

        # 2. SKU (Kód produktu)
        # Hľadáme v span.code alebo cez itemprop
        sku_element = soup.find('span', class_='code') or soup.find('span', itemprop='sku')
        kod_produktu = sku_element.get_text(strip=True) if sku_element else None
        
        # 3. Stav Skladu
        skladom_hodnota = 0 
        stock_span = soup.find('span', class_='availability-amount')
        if stock_span:
            stock_text = stock_span.get_text(strip=True)
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
    urls = get_all_product_urls(SITEMAP_URL)
    
    if urls:
        vysledky = []
        celkovo = len(urls)
        print(f"Štartujem spracovanie {celkovo} URL adries...")

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_url = {executor.submit(scrape_product_data, url): url for url in urls}
            
            spracovane = 0
            for future in as_completed(future_to_url):
                data = future.result()
                if data:
                    vysledky.append(data)
                
                spracovane += 1
                if spracovane % 100 == 0:
                    print(f"Progress: {spracovane}/{celkovo} | Nájdené produkty: {len(vysledky)}")

        if vysledky:
            df = pd.DataFrame(vysledky)
            df.drop_duplicates(subset=['SKU'], inplace=True)
            df.to_csv(VYSTUPNY_SUBOR, index=False, encoding='utf-8-sig', sep=';')
            print(f"HOTOVO! Uložených {len(df)} produktov do {VYSTUPNY_SUBOR}")
        else:
            print("Neboli nájdené žiadne platné dáta produktov.")
