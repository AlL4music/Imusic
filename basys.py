import time
import pandas as pd
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
import os

# --- NASTAVENIA ---
SITEMAP_URL = 'https://basys.sk/sitemap/sk/sitemap.xml'
VYSTUPNY_SUBOR = 'basys_sklad.csv'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Referer': 'https://basys.sk/'
}
MAX_WORKERS = 3 # Pri Basys radšej pomalšie (3-5), aby ťa neblokli

def scrape_product_data(url, session):
    try:
        response = session.get(url, timeout=15)
        if response.status_code != 200:
            print(f"!!! Blokované: {url} (Status {response.status_code})")
            return None 

        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extrakcia dát
        nazov_el = soup.find('h1', class_='col-xs-12')
        nazov = nazov_el.get_text(strip=True) if nazov_el else "N/A"
        
        sku_el = soup.find('span', itemprop='sku')
        sku = sku_el.get_text(strip=True) if sku_el else None
        
        skladom = 1 if soup.find('i', class_='av-7') else 0
        
        if sku:
            return {'SKU': sku, 'Nazov': nazov, 'Pocet_ks': skladom, 'URL': url}
    except Exception as e:
        print(f"!!! Chyba pri sťahovaní {url}: {e}")
    return None

if __name__ == "__main__":
    # Vždy vytvoríme súbor s hlavičkou na začiatku
    pd.DataFrame(columns=['SKU', 'Nazov', 'Pocet_ks', 'URL']).to_csv(VYSTUPNY_SUBOR, index=False, sep=';')
    
    urls = []
    # 1. KROK: Skúsime lokálnu sitemapu, ktorú si nahral
    if os.path.exists('sitemap_basys.xml'):
        print("DEBUG: Našiel som súbor sitemap_basys.xml v repozitári.")
        with open('sitemap_basys.xml', 'r', encoding='utf-8') as f:
            content = f.read()
            soup = BeautifulSoup(content, 'lxml-xml')
            urls = [loc.text for loc in soup.find_all('loc') if loc.text]
            
            # Ak sú adresy v sitemape iné ako .html, skúsime ich očistiť
            urls = [u.strip() for u in urls if '/sk/' in u and not u.endswith('.xml')]
            
        print(f"DEBUG: V sitemape som našiel {len(urls)} adries.")
        if urls:
            print(f"DEBUG: Prvých 5 adries: {urls[:5]}")
    else:
        print("DEBUG: Súbor sitemap_basys.xml NEBOL nájdený v aktuálnom priečinku.")

    # 2. KROK: Ak lokálna sitemapa zlyhala, skúsime web (len pre istotu)
    if not urls:
        print("Pokus o stiahnutie sitemapy z webu...")
        try:
            r = requests.get(SITEMAP_URL, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                soup = BeautifulSoup(r.content, 'lxml-xml')
                urls = [loc.text for loc in soup.find_all('loc') if loc.text and '/sk/' in loc.text]
        except:
            pass

    if not urls:
        print("CHYBA: Nepodarilo sa získať žiadne URL adresy produktov.")
        exit(0)

    # 3. KROK: Samotné sťahovanie
    print(f"Začínam sťahovať {len(urls)} produktov (vlákna: {MAX_WORKERS})...")
    vysledky = []
    with requests.Session() as session:
        session.headers.update(HEADERS)
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Na test vezmeme len prvých 200, aby si videl výsledok rýchlo
            futures = [executor.submit(scrape_product_data, url, session) for url in urls[:200]]
            for i, future in enumerate(futures):
                res = future.result()
                if res:
                    vysledky.append(res)
                if (i + 1) % 50 == 0:
                    print(f"Spracované: {i + 1}/{len(urls[:200])}")

    if vysledky:
        df = pd.DataFrame(vysledky)
        df.to_csv(VYSTUPNY_SUBOR, index=False, encoding='utf-8-sig', sep=';')
        print(f"HOTOVO! Súbor {VYSTUPNY_SUBOR} vytvorený s {len(vysledky)} položkami.")
    else:
        print("Žiadne dáta sa nepodarilo stiahnuť (pravdepodobne hromadná 403-ka).")
