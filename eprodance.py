import time
import re
import pandas as pd
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings

# Vypneme varovania BeautifulSoup, aby bol log na GitHube čistý
warnings.filterwarnings("ignore", category=UserWarning, module='bs4')

# --- NASTAVENIA ---
SITEMAP_URL = 'https://www.eprodance.cz/sitemap.xml'
VYSTUPNY_SUBOR = 'eprodance_sklad.csv'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

MAX_WORKERS = 15  # Rýchlejšie spracovanie
TIMEOUT = 15

session = requests.Session()
session.headers.update(HEADERS)

def get_all_product_urls(sitemap_url):
    print(f"Načítavam sitemapu z: {sitemap_url}")
    try:
        response = session.get(sitemap_url, timeout=30)
        response.raise_for_status()
        
        # DÔLEŽITÉ: Parsujeme ako XML a hľadáme len <loc> vo vnútri <url>
        soup = BeautifulSoup(response.content, 'lxml-xml')
        
        # Vytiahneme len texty z tagov <loc>, ktoré patria k <url> (ignorujeme tagy vnútri <image:image>)
        all_links = [url_tag.find('loc').text for url_tag in soup.find_all('url') if url_tag.find('loc')]
        
        # FILTER: Vyhodíme značky, kategórie a iný balast
        blacklist = ['/znacka/', '/clanky/', '/blog/', '/vyrobce/', '/kontakt', '/o-nas', '/kosik']
        
        product_urls = [
            url for url in all_links 
            if not any(b in url for b in blacklist)
            and url.endswith('/') # Produkty na eprodance zvyčajne končia lomkou
        ]
        
        # Odstránime duplicity (ak by tam boli)
        product_urls = list(set(product_urls))
        
        print(f"Nájdených {len(product_urls)} čistých produktových adries (ignorované značky a obrázky).")
        return product_urls
    except Exception as e:
        print(f"!!! CHYBA sitemapy: {e}")
        return []

def scrape_product_data(url):
    try:
        response = session.get(url, timeout=TIMEOUT)
        if response.status_code != 200:
            return None 

        # FIX PRE KÓDOVANIE: Dekódujeme bity na text a ignorujeme neplatné znaky
        html_text = response.content.decode('utf-8', errors='ignore')
        soup = BeautifulSoup(html_text, 'html.parser')

        # 1. Názov (H1)
        nazov_element = soup.find('h1')
        if not nazov_element: return None
        nazov_produktu = nazov_element.get_text(strip=True)

        # 2. SKU (Kód produktu) - Eprodance má kód v span.code
        sku_element = soup.find('span', class_='code') or soup.find('span', itemprop='sku')
        kod_produktu = sku_element.get_text(strip=True) if sku_element else None
        
        if not kod_produktu:
            # Záložný pokus cez text "Kód:"
            match_sku = soup.find(string=re.compile(r'Kód:'))
            if match_sku:
                kod_produktu = match_sku.parent.get_text(strip=True).replace('Kód:', '').strip()

        # 3. Sklad (Číslo v availability-amount)
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
        print(f"Štartujem spracovanie (vlákna: {MAX_WORKERS})...")

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_url = {executor.submit(scrape_product_data, url): url for url in urls}
            
            spracovane = 0
            for future in as_completed(future_to_url):
                data = future.result()
                if data:
                    vysledky.append(data)
                
                spracovane += 1
                if spracovane % 100 == 0:
                    print(f"Progress: {spracovane}/{celkovo} | Získané produkty: {len(vysledky)}")

        if vysledky:
            df = pd.DataFrame(vysledky)
            df.drop_duplicates(subset=['SKU'], inplace=True)
            df.to_csv(VYSTUPNY_SUBOR, index=False, encoding='utf-8-sig', sep=';')
            print(f"HOTOVO! Súbor {VYSTUPNY_SUBOR} uložený. Počet produktov: {len(df)}")
