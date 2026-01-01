import time
import re
import pandas as pd
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- NASTAVENIA ---
SITEMAP_URL = 'https://www.music-park.sk/sitemap.xml'
VYSTUPNY_SUBOR = 'musicpark_sklad.csv'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}
# Počet paralelných vlákien (odporúčam 5 až 15, aby vás server nezablokoval)
MAX_WORKERS = 10 

def get_all_product_urls(sitemap_url):
    print(f"Načítavam sitemapu z: {sitemap_url}")
    try:
        response = requests.get(sitemap_url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'lxml-xml')
        
        all_urls = [loc.text for loc in soup.find_all('loc') if loc.text]
        product_urls = [url for url in all_urls if '/produkt/' in url]
        
        print(f"Nájdených {len(product_urls)} produktov na kontrolu.")
        return product_urls
    except Exception as e:
        print(f"!!! CHYBA sitemapy: {e}")
        return []

def scrape_product_data(url, session):
    """Spracuje jeden produkt pomocou zdieľanej session"""
    try:
        response = session.get(url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            return None 

        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Názov
        nazov_element = soup.find('h1')
        nazov_produktu = nazov_element.get_text(strip=True) if nazov_element else "N/A"

        # SKU (Kód)
        kod_produktu = None
        sku_div = soup.find('div', string=re.compile(r'Obj\. kód:'))
        if sku_div:
            kod_produktu = sku_div.get_text(strip=True).split(':')[-1].strip().replace('\xa0', '')

        # Skladovosť
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
        pass
    return None

def run_turbo_scraper():
    urls = get_all_product_urls(SITEMAP_URL)
    if not urls:
        return

    vysledky = []
    total = len(urls)
    
    print(f"Spúšťam turbo sťahovanie s {MAX_WORKERS} vláknami...")
    
    # Použitie Session pre zrýchlenie sieťovej komunikácie
    with requests.Session() as session:
        # ThreadPoolExecutor zabezpečí paralelný beh
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Mapovanie úloh na vlákna
            future_to_url = {executor.submit(scrape_product_data, url, session): url for url in urls}
            
            for i, future in enumerate(as_completed(future_to_url)):
                data = future.result()
                if data:
                    vysledky.append(data)
                
                # Progress bar každých 50 produktov
                if (i + 1) % 50 == 0:
                    print(f"Spracované: {i + 1} / {total}")

    if vysledky:
        df = pd.DataFrame(vysledky)
        df.to_csv(VYSTUPNY_SUBOR, index=False, encoding='utf-8-sig', sep=';')
        print(f"--- HOTOVO! ---")
        print(f"Uložených {len(vysledky)} produktov do {VYSTUPNY_SUBOR}")

if __name__ == "__main__":
    start_time = time.time()
    run_turbo_scraper()
    duration = time.time() - start_time
    print(f"Celkový čas: {duration:.2f} sekúnd.")
