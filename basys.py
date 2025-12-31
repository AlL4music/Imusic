import time
import pandas as pd  # Toto definuje 'pd'
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
import os

# --- NASTAVENIA ---
SITEMAP_URL = 'https://basys.sk/sitemap/sk/sitemap.xml'
VYSTUPNY_SUBOR = 'basys_sklad.csv'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'sk-SK,sk;q=0.9,cs;q=0.8,en;q=0.7',
    'Referer': 'https://basys.sk/'
}

MAX_WORKERS = 5 

def get_all_product_urls():
    print(f"Pokus o načítanie sitemapy: {SITEMAP_URL}")
    try:
        response = requests.get(SITEMAP_URL, headers=HEADERS, timeout=30)
        if response.status_code == 403:
            print("!!! CHYBA 403: Web nás blokuje.")
            return []
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'lxml-xml')
        return [loc.text for loc in soup.find_all('loc') if loc.text and loc.text.endswith('.html')]
    except Exception as e:
        print(f"!!! CHYBA sitemapy: {e}")
        return []

def scrape_product_data(url, session):
    try:
        time.sleep(0.1) 
        response = session.get(url, timeout=15)
        response.encoding = 'utf-8'
        if response.status_code != 200: return None 

        soup = BeautifulSoup(response.content, 'html.parser')
        nazov_el = soup.find('h1', class_='col-xs-12')
        nazov = nazov_el.get_text(strip=True) if nazov_el else "N/A"
        sku_el = soup.find('span', itemprop='sku')
        sku = sku_el.get_text(strip=True) if sku_el else None

        skladom = 0 
        if soup.find('i', class_='av-7'): skladom = 1
        elif soup.find('i', class_='av-3'): skladom = 0
        
        if sku:
            return {'SKU': sku, 'Nazov': nazov, 'Pocet_ks': skladom, 'URL': url}
    except:
        pass
    return None

if __name__ == "__main__":
    # 1. Vytvoríme prázdny súbor hneď na začiatku (teraz už pd existuje!)
    pd.DataFrame(columns=['SKU', 'Nazov', 'Pocet_ks', 'URL']).to_csv(VYSTUPNY_SUBOR, index=False, sep=';')
    
    # 2. Skúsime lokálnu sitemapu (ak si ju už nahral na GitHub)
    urls = []
    if os.path.exists('sitemap_basys.xml'):
        print("Používam lokálnu sitemapu sitemap_basys.xml...")
        with open('sitemap_basys.xml', 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f.read(), 'lxml-xml')
            urls = [loc.text for loc in soup.find_all('loc') if loc.text and loc.text.endswith('.html')]
    
    # 3. Ak lokálna nie je, skúsime web
    if not urls:
        urls = get_all_product_urls()

    if not urls:
        print("Koniec: Žiadne URL adresy. Nezabudni nahrať sitemap_basys.xml!")
        exit(0)

    print(f"Spracovávam {len(urls)} produktov...")
    vysledky = []
    with requests.Session() as session:
        session.headers.update(HEADERS)
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(scrape_product_data, url, session) for url in urls]
            for i, future in enumerate(futures):
                res = future.result()
                if res: vysledky.append(res)
                if (i + 1) % 50 == 0: print(f"Spracované: {i + 1}/{len(urls)}")

    if vysledky:
        pd.DataFrame(vysledky).to_csv(VYSTUPNY_SUBOR, index=False, encoding='utf-8-sig', sep=';')
        print(f"HOTOVO! Súbor vytvorený.")
