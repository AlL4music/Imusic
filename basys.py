import time
import pandas as pd
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
import os
import re

# --- NASTAVENIA ---
VYSTUPNY_SUBOR = 'basys_sklad.csv'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Referer': 'https://www.basys.sk/'
}
MAX_WORKERS = 5 # Basys je citlivý, 5 je bezpečný stred

def scrape_product_data(url, session):
    try:
        # Malá pauza, aby sme nepôsobili ako agresívny útok
        time.sleep(0.3)
        response = session.get(url, timeout=15)
        if response.status_code != 200:
            return None 

        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 1. Názov
        nazov_el = soup.find('h1', class_='col-xs-12')
        nazov = nazov_el.get_text(strip=True) if nazov_el else "N/A"
        
        # 2. SKU (Kód produktu)
        sku_el = soup.find('span', itemprop='sku')
        sku = sku_el.get_text(strip=True) if sku_el else None
        
        # 3. Stav skladu (av-7 = na sklade, av-3 = nie je)
        skladom = 1 if soup.find('i', class_='av-7') else 0
        
        if sku:
            return {'SKU': sku, 'Nazov': nazov, 'Pocet_ks': skladom, 'URL': url}
    except:
        pass
    return None

if __name__ == "__main__":
    # Vytvoríme prázdny CSV hneď na štart
    pd.DataFrame(columns=['SKU', 'Nazov', 'Pocet_ks', 'URL']).to_csv(VYSTUPNY_SUBOR, index=False, sep=';')
    
    urls = []
    
    # KROK 1: Načítanie z tvojho lokálneho XML súboru
    if os.path.exists('sitemap_basys.xml'):
        print("DEBUG: Čítam lokálny súbor sitemap_basys.xml...")
        with open('sitemap_basys.xml', 'r', encoding='utf-8') as f:
            content = f.read()
            # Použijeme veľmi voľný regulárny výraz na vytiahnutie všetkých linkov v <loc>
            urls = re.findall(r'<loc>(https?://[^<]+)</loc>', content)
        
        # Filter: Zoberieme všetko, čo končí na .html a nie je to kategória (/c/)
        urls = [u.strip() for u in urls if u.endswith('.html') and '/c/' not in u]
        print(f"DEBUG: V lokálnom XML som našiel {len(urls)} adries.")
    else:
        print("DEBUG: Súbor sitemap_basys.xml NEBOL NÁJDENÝ!")

    if not urls:
        print("!!! CHYBA: Zoznam URL je prázdny. Skript končí.")
        exit(0)

    # KROK 2: Sťahovanie produktov
    print(f"Spúšťam sťahovanie pre {len(urls)} produktov (vlákna: {MAX_WORKERS})...")
    vysledky = []
    
    with requests.Session() as session:
        session.headers.update(HEADERS)
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Spustíme sťahovanie pre všetky nájdené adresy
            futures = [executor.submit(scrape_product_data, url, session) for url in urls]
            
            for i, future in enumerate(futures):
                res = future.result()
                if res:
                    vysledky.append(res)
                
                if (i + 1) % 50 == 0:
                    print(f"Postup: {i + 1}/{len(urls)}")

    # KROK 3: Uloženie
    if vysledky:
        df = pd.DataFrame(vysledky)
        df.to_csv(VYSTUPNY_SUBOR, index=False, encoding='utf-8-sig', sep=';')
        print(f"HOTOVO! Uložených {len(vysledky)} produktov.")
    else:
        print("!!! CHYBA: Žiadne produkty neboli úspešne stiahnuté (skontroluj logy vyššie).")
