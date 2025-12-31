import time
import re
import pandas as pd
import requests
from bs4 import BeautifulSoup
import os

# --- NASTAVENIA ---
SITEMAP_URL = 'https://www.alexim.cz/sitemap.xml'
VYSTUPNY_SUBOR = 'alexim_sklad.csv'
URL_LIST_FILE = 'urls_to_process.txt'
PROGRESS_FILE = 'last_index.txt'
BATCH_SIZE = 50  # Koľko produktov spracuje pri jednom spustení
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...'}
PAUZA_MEDZI_POZIADAVKAMI = 0.2

def get_all_product_urls(sitemap_url):
    if os.path.exists(URL_LIST_FILE):
        with open(URL_LIST_FILE, 'r') as f:
            return [line.strip() for line in f.readlines()]
    
    print("Sťahujem sitemapu nanovo...")
    try:
        response = requests.get(sitemap_url, headers=HEADERS, timeout=30)
        soup = BeautifulSoup(response.content, 'lxml-xml')
        all_urls = [loc.text for loc in soup.find_all('loc') if loc.text]
        product_urls = [url for url in all_urls if '/c/' not in url and '/v/' not in url and '/clanky/' not in url]
        
        with open(URL_LIST_FILE, 'w') as f:
            for url in product_urls:
                f.write(f"{url}\n")
        return product_urls
    except Exception as e:
        print(f"Chyba sitemapy: {e}")
        return []

def scrape_product_data(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code != 200: return None
        soup = BeautifulSoup(response.content, 'html.parser')
        
        nazov_element = soup.find('h1', class_='product-detail__title')
        nazov_produktu = nazov_element.get_text(strip=True) if nazov_element else "N/A"

        sku_element = soup.find('strong', string=re.compile(r'^\d+\.\d+$'))
        if not sku_element:
            sku_element = soup.find('strong', itemprop='sku') or soup.find('span', itemprop='sku')
        
        kod_produktu = sku_element.get_text(strip=True) if sku_element else None
        
        skladom_hodnota = 1 if soup.find('strong', string=re.compile(r'skladem', re.IGNORECASE)) else 0
        
        if kod_produktu:
            return {'SKU': kod_produktu, 'Nazov': nazov_produktu, 'Pocet_ks': skladom_hodnota, 'URL': url}
    except:
        return None

if __name__ == "__main__":
    urls = get_all_product_urls(SITEMAP_URL)
    
    # Načítanie progresu
    start_index = 0
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            start_index = int(f.read().strip())

    if start_index >= len(urls):
        print("Všetko je už spracované. Ak chceš začať odznova, zmaž last_index.txt.")
        exit()

    end_index = min(start_index + BATCH_SIZE, len(urls))
    vysledky = []

    print(f"Spracovávam dávku: {start_index} až {end_index} (celkovo {len(urls)})")

    for i in range(start_index, end_index):
        data = scrape_product_data(urls[i])
        if data:
            vysledky.append(data)
        time.sleep(PAUZA_MEDZI_POZIADAVKAMI)

    # Uloženie dát (Mód 'a' - append pridáva na koniec súboru)
    if vysledky:
        df = pd.DataFrame(vysledky)
        # Pridať hlavičku len ak súbor ešte neexistuje
        header = not os.path.exists(VYSTUPNY_SUBOR)
        df.to_csv(VYSTUPNY_SUBOR, mode='a', index=False, header=header, encoding='utf-8-sig', sep=';')

    # Aktualizácia progresu
    with open(PROGRESS_FILE, 'w') as f:
        f.write(str(end_index))
    
    print(f"Hotovo. Nabudúce začíname od indexu {end_index}")
