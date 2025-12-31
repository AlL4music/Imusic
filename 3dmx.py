import time
import re
import pandas as pd
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

# --- NASTAVENIA ---
SITEMAP_URL = 'https://www.3dmx.cz/sitemap/sitemap_cs.xml'
VYSTUPNY_SUBOR = '3dmx_sklad.csv'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}
MAX_WORKERS = 15  # Počet paralelných robotov (15 je pre tento typ webu ideál)

def get_all_product_urls():
    print(f"Načítavam sitemapu: {SITEMAP_URL}")
    try:
        response = requests.get(SITEMAP_URL, headers=HEADERS, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'lxml-xml')
        
        # Načítame všetky lokácie
        all_urls = [loc.text for loc in soup.find_all('loc') if loc.text]
        
        # Filter: Odstránime kategórie (/c/) a výrobcov (/vyr/)
        filtered_urls = [url for url in all_urls if '/c/' not in url and '/vyr/' not in url]
        
        print(f"Nájdených {len(filtered_urls)} produktových URL.")
        return filtered_urls
    except Exception as e:
        print(f"!!! CHYBA sitemapy: {e}")
        return []

def scrape_product_data(url, session):
    """Spracuje jeden konkrétny produkt pomocou pridelenej session"""
    try:
        response = session.get(url, timeout=15)
        response.encoding = 'utf-8' # Zabezpečí správne české znaky
        if response.status_code != 200:
            return None 

        soup = BeautifulSoup(response.content, 'html.parser')

        # 1. Kód produktu (SKU)
        sku_td = soup.find('td', class_='td_katalog_detail_polozka')
        kod_produktu = sku_td.get_text(strip=True) if sku_td else None

        # 2. Názov
        nazov_element = soup.find('h1')
        nazov_produktu = nazov_element.get_text(strip=True) if nazov_element else "N/A"

        # 3. Stav Skladu
        skladom_hodnota = 0 
        stock_span = soup.find('span', class_='skladem')
        if stock_span:
            stock_text = stock_span.get_text(strip=True).lower()
            match = re.search(r'(\d+)', stock_text)
            if match:
                skladom_hodnota = int(match.group(1))
            elif any(x in stock_text for x in ["skladem", "ano", "ihned"]):
                skladom_hodnota = 1
        
        if kod_produktu:
            return {
                'SKU': kod_produktu,
                'Nazov': nazov_produktu,
                'Pocet_ks': skladom_hodnota,
                'URL': url
            }
    except:
        pass
    return None

if __name__ == "__main__":
    urls = get_all_product_urls()
    if not urls:
        print("Žiadne URL na spracovanie.")
        exit()

    vysledky = []
    start_time = time.time()
    print(f"Spúšťam turbo sťahovanie cez {MAX_WORKERS} vlákien...")

    #requests.Session() zrýchľuje prácu, lebo recykluje pripojenie
    with requests.Session() as session:
        session.headers.update(HEADERS)
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Rozdelíme prácu medzi vlákna
            futures = [executor.submit(scrape_product_data, url, session) for url in urls]
            
            for i, future in enumerate(futures):
                result = future.result()
                if result:
                    vysledky.append(result)
                
                if (i + 1) % 100 == 0:
                    print(f"Spracované: {i + 1}/{len(urls)}...")

    if vysledky:
        df = pd.DataFrame(vysledky)
        df.to_csv(VYSTUPNY_SUBOR, index=False, encoding='utf-8-sig', sep=';')
        
        trvanie = (time.time() - start_time) / 60
        print(f"HOTOVO! {len(vysledky)} položiek spracovaných za {trvanie:.2f} minút.")
