import re
import json
import pandas as pd
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings

# Úplné stíšenie BeautifulSoup varovaní
warnings.filterwarnings("ignore", category=UserWarning, module='bs4')

# --- NASTAVENIA ---
SITEMAP_URL = 'https://www.musictrade.cz/sitemap.xml'
VYSTUPNY_SUBOR = 'musictrade_sklad.csv'
THREADS = 20  # Môžeš skúsiť aj 20, keďže sme vyhodili UI záťaž
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

session = requests.Session()
session.headers.update(HEADERS)

def get_all_product_urls(sitemap_url):
    print(f"Sťahujem sitemapu...")
    try:
        response = session.get(sitemap_url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'lxml-xml')
        all_urls = [loc.text for loc in soup.find_all('loc') if loc.text]
        product_urls = [url for url in all_urls if '/znacka/' not in url and '/kategorie/' not in url]
        return product_urls
    except Exception as e:
        print(f"Chyba sitemapy: {e}")
        return []

def scrape_product_data(url):
    try:
        response = session.get(url, timeout=10)
        if response.status_code != 200:
            return None

        response.encoding = response.apparent_encoding 
        soup = BeautifulSoup(response.content, 'lxml', from_encoding='utf-8')
        
        scripts = soup.find_all('script')
        data_script = next((s.string for s in scripts if s.string and 'dataLayer.push' in s.string and '"product":' in s.string), None)
        
        if not data_script:
            return None

        match = re.search(r'"product":\s*({.*?"priceWithVat":.*?})\s*,', data_script, re.DOTALL)
        if not match:
            return None
        
        product_data = json.loads(match.group(1).replace(r'\/', '/'))
        
        skladom_hodnota = 0
        if product_data.get('codes'):
            quantity_str = product_data['codes'][0].get('quantity')
            if quantity_str:
                quantity_clean = str(quantity_str).replace('>', '').strip()
                try:
                    skladom_hodnota = int(quantity_clean)
                except ValueError:
                    skladom_hodnota = 1 
        
        return {
            'SKU': product_data.get('code'),
            'Nazov': product_data.get('name'),
            'Pocet_ks': skladom_hodnota,
            'URL': url
        }
    except:
        return None

if __name__ == "__main__":
    urls = get_all_product_urls(SITEMAP_URL)
    
    START_INDEX = 400
    urls_na_spracovanie = urls[START_INDEX:] if len(urls) > START_INDEX else []
    total = len(urls_na_spracovanie)
    
    if not urls_na_spracovanie:
        print("Žiadne dáta.")
    else:
        vysledky = []
        print(f"Štart scrapingu: {total} produktov ({THREADS} vlákien)")
        
        with ThreadPoolExecutor(max_workers=THREADS) as executor:
            futures = {executor.submit(scrape_product_data, url): url for url in urls_na_spracovanie}
            
            counter = 0
            for future in as_completed(futures):
                counter += 1
                data = future.result()
                if data:
                    vysledky.append(data)
                
                # Logujeme len každých 500 kusov, aby bol log čistý a rýchly
                if counter % 500 == 0:
                    print(f"Spracované: {counter}/{total}")

        if vysledky:
            pd.DataFrame(vysledky).to_csv(VYSTUPNY_SUBOR, index=False, encoding='utf-8-sig', sep=';')
            print(f"Hotovo. Uložených {len(vysledky)} položiek.")
