import time
import re
import pandas as pd
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- NASTAVENIA ---
SITEMAP_URL = 'https://www.eprodance.cz/sitemap.xml'
VYSTUPNY_SUBOR = 'eprodance_sklad.csv'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# TURBO NASTAVENIA
MAX_WORKERS = 15  # Zvýšené na 15 pre rýchlejšie spracovanie 15k produktov
TIMEOUT = 15

def get_all_product_urls(sitemap_url):
    print(f"Načítavam sitemapu z: {sitemap_url}")
    try:
        response = requests.get(sitemap_url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        # Pri sitemape používame content, lxml-xml si s tým poradí
        soup = BeautifulSoup(response.content, 'lxml-xml')
        
        all_urls = [loc.text for loc in soup.find_all('loc') if loc.text]
        # Filtrujeme len produktové URL (obsahujúce /p/)
        product_urls = [url for url in all_urls if '/p/' in url]
        
        print(f"Nájdených {len(product_urls)} produktových URL adries.")
        return product_urls
    except Exception as e:
        print(f"!!! CHYBA sitemapy: {e}")
        return None

def scrape_product_data(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if response.status_code != 200:
            return None 

        # --- OPRAVA KÓDOVANIA ---
        # Nastavíme kódovanie podľa toho, čo deteguje requests (vyrieši "REPLACEMENT CHARACTER")
        response.encoding = response.apparent_encoding 
        
        # Použijeme response.text (už dekódovaný string) namiesto response.content
        soup = BeautifulSoup(response.text, 'html.parser')

        # 1. Názov
        nazov_element = soup.find('h1')
        nazov_produktu = nazov_element.get_text(strip=True) if nazov_element else "N/A"

        # 2. Kód produktu (SKU)
        sku_element = soup.find('span', class_='code') or soup.find('span', itemprop='sku')
        if not sku_element:
             match_sku = soup.find(string=re.compile(r'Kód:'))
             kod_produktu = match_sku.parent.get_text(strip=True).replace('Kód:', '').strip() if match_sku else None
        else:
             kod_produktu = sku_element.get_text(strip=True)

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
        print(f"Štartujem spracovanie (vlákien: {MAX_WORKERS}). Prosím čakajte...")

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_url = {executor.submit(scrape_product_data, url): url for url in urls}
            
            spracovane = 0
            for future in as_completed(future_to_url):
                data = future.result()
                if data:
                    vysledky.append(data)
                
                spracovane += 1
                if spracovane % 100 == 0:
                    print(f"Progress: {spracovane}/{celkovo} (Získaných {len(vysledky)} produktov)")

        if vysledky:
            df = pd.DataFrame(vysledky)
            # Odstránenie duplicít a uloženie
            df.drop_duplicates(subset=['SKU'], inplace=True)
            df.to_csv(VYSTUPNY_SUBOR, index=False, encoding='utf-8-sig', sep=';')
            print(f"--- HOTOVO ---")
            print(f"Spracovaných: {spracovane} URL")
            print(f"Uložených produktov: {len(df)}")
            print(f"Súbor: {VYSTUPNY_SUBOR}")
