import time
import pandas as pd
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
import os

# --- NASTAVENIA ---
SITEMAP_URL = 'https://basys.sk/sitemap/sk/sitemap.xml'
VYSTUPNY_SUBOR = 'basys_sklad.csv'

# Vylepšené hlavičky (Headers) aby sme vyzerali ako reálny Chrome prehliadač
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'sk-SK,sk;q=0.9,cs;q=0.8,en;q=0.7',
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache',
    'Referer': 'https://basys.sk/',
    'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '"Windows"',
}

# Znížime počet robotov na 5, aby nás server nevyhodnotil ako útok
MAX_WORKERS = 5 

def get_all_product_urls():
    print(f"Pokus o načítanie sitemapy: {SITEMAP_URL}")
    try:
        # Použijeme Session aj na sitemapu
        session = requests.Session()
        response = session.get(SITEMAP_URL, headers=HEADERS, timeout=30)
        
        if response.status_code == 403:
            print("!!! CHYBA 403: Server nás stále blokuje. Skúsime alternatívu...")
            return []
            
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'lxml-xml')
        
        product_urls = [loc.text for loc in soup.find_all('loc') if loc.text and loc.text.endswith('.html')]
        print(f"Nájdených {len(product_urls)} produktových URL adries.")
        return product_urls
    except Exception as e:
        print(f"!!! CHYBA sitemapy: {e}")
        return []

def scrape_product_data(url, session):
    try:
        # Malá náhodná pauza, aby sme neboli príliš nápadní
        time.sleep(0.1) 
        response = session.get(url, headers=HEADERS, timeout=15)
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
    # Vytvoríme súbor hneď na začiatku kvôli GitHubu
    pd.DataFrame(columns=['SKU', 'Nazov', 'Pocet_ks', 'URL']).to_csv(VYSTUPNY_SUBOR, index=False, sep=';')
    
    urls = get_all_product_urls()
    
    # AK SITEMAPA ZLYHÁ (403), TU JE PLAN B:
    if not urls:
        print("Sitemapa zlyhala. Skúšam hľadať lokálnu sitemapu (sitemap_basys.xml)...")
        if os.path.exists('sitemap_basys.xml'):
            with open('sitemap_basys.xml', 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f.read(), 'lxml-xml')
                urls = [loc.text for loc in soup.find_all('loc') if loc.text and loc.text.endswith('.html')]
                print(f"Načítaných {len(urls)} URL z lokálneho súboru.")

    if not urls:
        print("Koniec: Žiadne URL na spracovanie.")
        exit(0)

    vysledky = []
    with requests.Session() as session:
        # Nastavíme HEADERS pre celú session
        session.headers.update(HEADERS)
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(scrape_product_data, url, session) for url in urls]
            for i, future in enumerate(futures):
                res = future.result()
                if res:
                    vysledky.append(res)
                if (i + 1) % 50 == 0:
                    print(f"Spracované: {i + 1}/{len(urls)}")

    if vysledky:
        df = pd.DataFrame(vysledky)
        df.to_csv(VYSTUPNY_SUBOR, index=False, encoding='utf-8-sig', sep=';')
        print(f"HOTOVO! Súbor vytvorený s {len(vysledky)} položkami.")
    else:
        print("Súbor ostáva prázdny.")
