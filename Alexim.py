import time
import re
import pandas as pd
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

SITEMAP_URL = 'https://www.alexim.cz/sitemap.xml'
VYSTUPNY_SUBOR = 'alexim_sklad.csv'
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
MAX_WORKERS = 15

def get_product_urls():
    print("Stahujem sitemapu...")
    try:
        r = requests.get(SITEMAP_URL, headers=HEADERS, timeout=30)
        soup = BeautifulSoup(r.content, 'lxml-xml')
        urls = [loc.text for loc in soup.find_all('loc') if loc.text]
        return [u for u in urls if not any(x in u for x in ['/c/', '/v/', '/clanky/', '/images/', '/p/', '.jpg', '.png', '.pdf'])]
    except Exception as e:
        print(f"Chyba: {e}")
        return []

def scrape_product(url, session):
    try:
        res = session.get(url, timeout=15)
        res.encoding = 'utf-8'
        if res.status_code != 200: return None
        soup = BeautifulSoup(res.content, 'html.parser')
        nazov_el = soup.find('h1', class_='product-detail__title')
        nazov = nazov_el.get_text(strip=True) if nazov_el else "N/A"
        sku_el = soup.find('strong', string=re.compile(r'^\d+\.\d+$')) or \
                 soup.find('strong', itemprop='sku') or \
                 soup.find('span', itemprop='sku')
        sku = sku_el.get_text(strip=True) if sku_el else None
        stock = 1 if soup.find('strong', string=re.compile(r'skladem', re.IGNORECASE)) else 0
        if sku:
            return {'SKU': sku, 'Nazov': nazov, 'Pocet_ks': stock, 'URL': url}
    except:
        pass
    return None

if __name__ == "__main__":
    urls = get_product_urls()
    vysledky = []
    start_time = time.time()
    
    if urls:
        print(f"Spracovavam {len(urls)} produktov...")
        with requests.Session() as session:
            session.headers.update(HEADERS)
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = [executor.submit(scrape_product, url, session) for url in urls]
                for i, future in enumerate(futures):
                    res = future.result()
                    if res: vysledky.append(res)
                    if (i + 1) % 100 == 0: print(f"Postup: {i+1}/{len(urls)}")

    if vysledky:
        df = pd.DataFrame(vysledky)
    else:
        df = pd.DataFrame(columns=['SKU', 'Nazov', 'Pocet_ks', 'URL'])

    df.to_csv(VYSTUPNY_SUBOR, index=False, encoding='utf-8-sig')
    print(f"Hotovo za {(time.time() - start_time)/60:.2f} min.")
