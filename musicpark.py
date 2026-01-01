import time
import re
import pandas as pd
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

# --- NASTAVENIA ---
SITEMAP_URL = 'https://www.music-park.sk/sitemap.xml'
VYSTUPNY_SUBOR = 'musicpark_sklad.csv'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
}
MAX_WORKERS = 5 # Menej je niekedy viac, skúsime byť nenápadní

def get_product_urls():
    # flush=True vynúti okamžitý výpis na Githube
    print(f"Krok 1: Sťahujem sitemapu...", flush=True)
    try:
        r = requests.get(SITEMAP_URL, headers=HEADERS, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, 'lxml-xml')
        urls = [loc.text for loc in soup.find_all('loc') if '/produkt/' in loc.text]
        print(f"Nájdených {len(urls)} produktov.", flush=True)
        return urls
    except Exception as e:
        print(f"!!! Kritická chyba sitemapy: {e}", flush=True)
        return []

def scrape_product(url, session):
    try:
        res = session.get(url, timeout=10)
        if res.status_code != 200: return None
        
        soup = BeautifulSoup(res.content, 'html.parser')
        
        # SKU / Názov / Sklad (Logika Music-Park)
        kod = None
        sku_div = soup.find('div', string=re.compile(r'Obj\. kód:'))
        if sku_div:
            kod = sku_div.get_text(strip=True).split(':')[-1].strip().replace('\xa0', '')
        
        nazov_el = soup.find('h1')
        nazov = nazov_el.get_text(strip=True) if nazov_el else "N/A"
        
        stock = 0
        stock_span = soup.find('span', class_='dostupnost')
        if stock_span and 'skladom' in stock_span.get_text().lower():
            match = re.search(r'(\d+)', stock_span.get_text())
            stock = int(match.group(1)) if match else 1

        if kod:
            return {'SKU': kod, 'Nazov': nazov, 'Pocet_ks': stock, 'URL': url}
    except:
        pass
    return None

if __name__ == "__main__":
    urls = get_product_urls()
    
    # GARANCIA SÚBORU: Aj keď nič nenájde, vytvorí prázdne CSV, aby Git nepadol
    if not urls:
        print("Vytváram prázdny súbor (poistka pre Git).", flush=True)
        pd.DataFrame(columns=['SKU', 'Nazov', 'Pocet_ks', 'URL']).to_csv(VYSTUPNY_SUBOR, index=False, sep=';')
        exit()

    vysledky = []
    print(f"Krok 2: Štartujem sťahovanie...", flush=True)

    with requests.Session() as session:
        session.headers.update(HEADERS)
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(scrape_product, url, session) for url in urls[:100]] # TEST na prvých 100
            
            for i, future in enumerate(futures):
                res = future.result()
                if res: vysledky.append(res)
                if (i + 1) % 20 == 0:
                    print(f"Postup: {i + 1}/{len(futures)}", flush=True)

    # Uloženie (vždy prepíše súbor novými dátami)
    df = pd.DataFrame(vysledky if vysledky else columns=['SKU', 'Nazov', 'Pocet_ks', 'URL'])
    df.to_csv(VYSTUPNY_SUBOR, index=False, encoding='utf-8-sig', sep=';')
    print(f"Hotovo. Uložené: {len(vysledky)} riadkov.", flush=True)
