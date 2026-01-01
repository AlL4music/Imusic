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
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}
MAX_WORKERS = 10 # Odporúčam začať s 10 na GitHub Actions

def get_product_urls():
    print("Sťahujem sitemapu Music-Park...")
    try:
        r = requests.get(SITEMAP_URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
        # Používame lxml-xml pre sitemapy
        soup = BeautifulSoup(r.content, 'lxml-xml')
        all_urls = [loc.text for loc in soup.find_all('loc') if loc.text]
        
        # Filter pre Music-Park produkty
        filtered = [u for u in all_urls if '/produkt/' in u]
        print(f"Nájdených {len(filtered)} produktov.")
        return filtered
    except Exception as e:
        print(f"Chyba sitemapy: {e}")
        return []

def scrape_product(url, session):
    try:
        res = session.get(url, timeout=15)
        res.encoding = 'utf-8'
        if res.status_code != 200: 
            return None
        
        soup = BeautifulSoup(res.content, 'html.parser')
        
        # Extrakcia názvu
        nazov_el = soup.find('h1')
        nazov = nazov_el.get_text(strip=True) if nazov_el else "N/A"

        # Extrakcia SKU (Obj. kód)
        kod_produktu = None
        sku_div = soup.find('div', string=re.compile(r'Obj\. kód:'))
        if sku_div:
            kod_produktu = sku_div.get_text(strip=True).split(':')[-1].strip().replace('\xa0', '')
        
        # Extrakcia skladovosti
        stock = 0
        stock_span = soup.find('span', class_='dostupnost')
        if stock_span:
            stock_text = stock_span.get_text(strip=True).lower()
            if 'skladom' in stock_text:
                match = re.search(r'skladom (\d+)', stock_text)
                stock = int(match.group(1)) if match else 1
        
        if kod_produktu:
            return {'SKU': kod_produktu, 'Nazov': nazov, 'Pocet_ks': stock, 'URL': url}
    except:
        pass
    return None

if __name__ == "__main__":
    urls = get_product_urls()
    
    # POISTKA: Ak by sitemap nič nenašla, vytvoríme prázdne CSV s hlavičkou, aby GitHub nezlyhal
    if not urls:
        print("Žiadne URL na spracovanie. Vytváram prázdny súbor.")
        pd.DataFrame(columns=['SKU', 'Nazov', 'Pocet_ks', 'URL']).to_csv(VYSTUPNY_SUBOR, index=False, sep=';')
        exit()

    vysledky = []
    start_time = time.time()
    print(f"Spúšťam hromadné sťahovanie (Music-Park) cez {MAX_WORKERS} vlákien...")

    with requests.Session() as session:
        session.headers.update(HEADERS)
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Vytvorenie zoznamu úloh (Alexim štýl)
            futures = [executor.submit(scrape_product, url, session) for url in urls]
            
            for i, future in enumerate(futures):
                result = future.result()
                if result:
                    vysledky.append(result)
                
                if (i + 1) % 50 == 0:
                    print(f"Postup: {i + 1}/{len(urls)}")

    # Uloženie dát
    if vysledky:
        df = pd.DataFrame(vysledky)
        df.to_csv(VYSTUPNY_SUBOR, index=False, encoding='utf-8-sig', sep=';')
        print(f"HOTOVO! {len(vysledky)} produktov spracovaných.")
    else:
        # Ak by sa nič nepodarilo stiahnuť, vytvoríme aspoň súbor s hlavičkou
        pd.DataFrame(columns=['SKU', 'Nazov', 'Pocet_ks', 'URL']).to_csv(VYSTUPNY_SUBOR, index=False, sep=';')
        print("Nenašli sa žiadne dáta, súbor vytvorený ako prázdny.")
