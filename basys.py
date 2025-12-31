import time
import pandas as pd
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

# --- NASTAVENIA ---
SITEMAP_URL = 'https://basys.sk/sitemap/sk/sitemap.xml'
VYSTUPNY_SUBOR = 'basys_sklad.csv'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}
MAX_WORKERS = 15  # Počet paralelných robotov

def get_all_product_urls():
    print(f"Načítavam sitemapu: {SITEMAP_URL}")
    try:
        response = requests.get(SITEMAP_URL, headers=HEADERS, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'lxml-xml')
        
        # Filtrujeme len produktové URL (končiace .html)
        product_urls = [loc.text for loc in soup.find_all('loc') if loc.text and loc.text.endswith('.html')]
        
        print(f"Nájdených {len(product_urls)} produktových URL adries.")
        return product_urls
    except Exception as e:
        print(f"!!! CHYBA sitemapy: {e}")
        return []

def scrape_product_data(url, session):
    """Spracuje jeden konkrétny produkt z Basys.sk"""
    try:
        response = session.get(url, timeout=15)
        # Basys používa štandardne UTF-8
        response.encoding = 'utf-8'
        if response.status_code != 200:
            return None 

        soup = BeautifulSoup(response.content, 'html.parser')

        # 1. Názov
        nazov_element = soup.find('h1', class_='col-xs-12')
        nazov_produktu = nazov_element.get_text(strip=True) if nazov_element else "N/A"

        # 2. Kód produktu (SKU)
        sku_element = soup.find('span', itemprop='sku')
        kod_produktu = sku_element.get_text(strip=True) if sku_element else None

        # 3. Stav Skladu
        # Trieda av-7 = na sklade (1), trieda av-3 = nie je na sklade (0)
        skladom_hodnota = 0 
        if soup.find('i', class_='av-7'):
            skladom_hodnota = 1
        elif soup.find('i', class_='av-3'):
            skladom_hodnota = 0
        
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
    print(f"Spúšťam turbo sťahovanie pre Basys ({len(urls)} produktov)...")

    # Použitie Session pre zrýchlenie
    with requests.Session() as session:
        session.headers.update(HEADERS)
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Mapujeme sťahovanie na všetky URL
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
        print(f"HOTOVO! {len(vysledky)} položiek uložených za {trvanie:.2f} minút.")
