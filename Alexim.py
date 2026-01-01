import time
import re
import pandas as pd
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

# --- NASTAVENIA ---
SITEMAP_URL = 'https://www.alexim.cz/sitemap.xml'
VYSTUPNY_SUBOR = 'alexim_sklad.csv'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}
MAX_WORKERS = 15  # Počet paralelných sťahovaní

def get_product_urls():
    print("Sťahujem sitemapu a filtrujem produktové adresy...")
    try:
        r = requests.get(SITEMAP_URL, headers=HEADERS, timeout=30)
        soup = BeautifulSoup(r.content, 'lxml-xml')
        all_urls = [loc.text for loc in soup.find_all('loc') if loc.text]
        
        # Filter: Zahodíme obrázky, kategórie, články atď.
        filtered = [u for u in all_urls if not any(x in u for x in ['/c/', '/v/', '/clanky/', '/images/', '/p/', '.jpg', '.png', '.pdf'])]
        print(f"Nájdených {len(filtered)} produktov.")
        return filtered
    except Exception as e:
        print(f"Chyba sitemapy: {e}")
        return []

def scrape_product(url, session):
    """Funkcia pre jedno vlákno na stiahnutie dát produktu"""
    try:
        res = session.get(url, timeout=15)
        res.encoding = 'utf-8' # Oprava kódovania češtiny
        if res.status_code != 200:
            return None
        
        soup = BeautifulSoup(res.content, 'html.parser')
        
        # Extrakcia názvu
        nazov_el = soup.find('h1', class_='product-detail__title')
        nazov = nazov_el.get_text(strip=True) if nazov_el else "N/A"

        # Extrakcia SKU (skúša viacero možností, kde sa kód môže nachádzať)
        sku_el = soup.find('strong', string=re.compile(r'^\d+\.\d+$')) or \
                 soup.find('strong', itemprop='sku') or \
                 soup.find('span', itemprop='sku')
        sku = sku_el.get_text(strip=True) if sku_el else None
        
        # Zisťovanie skladu (hľadá text "skladem")
        stock = 1 if soup.find('strong', string=re.compile(r'skladem', re.IGNORECASE)) else 0
        
        if sku:
            return {'SKU': sku, 'Nazov': nazov, 'Pocet_ks': stock, 'URL': url}
    except Exception:
        pass
    return None

if __name__ == "__main__":
    urls = get_product_urls()
    if not urls:
        print("Žiadne URL na spracovanie.")
        exit()

    vysledky = []
    start_time = time.time()
    print(f"Spúšťam hromadné sťahovanie cez {MAX_WORKERS} vlákien...")

    with requests.Session() as session:
        session.headers.update(HEADERS)
        
        # Paralelné spracovanie všetkých URL adries
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(scrape_product, url, session) for url in urls]
            
            for i, future in enumerate(futures):
                result = future.result()
                if result:
                    vysledky.append(result)
                
                # Priebežný výpis stavu každých 100 produktov
                if (i + 1) % 100 == 0:
                    print(f"Postup: {i + 1}/{len(urls)}")

    # Spracovanie a uloženie výsledkov
    if vysledky:
        df = pd.DataFrame(vysledky)
    else:
        df = pd.DataFrame(columns=['SKU', 'Nazov', 'Pocet_ks', 'URL'])

    # Uloženie do CSV súboru
    try:
        df.to_csv(VYSTUPNY_SUBOR, index=False, encoding='utf-8-sig')
        trvanie = (time.time() - start_time) / 60
        print("-" * 30)
        print(f"HOTOVO! {len(vysledky)} produktov spracovaných za {trvanie:.2f} minút.")
        print(f"Súbor uložený ako: {VYSTUPNY_SUBOR}")
    except Exception as e:
        print(f"Chyba pri ukladaní súboru: {e}")
