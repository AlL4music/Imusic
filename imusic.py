import time
import gzip
import io
import pandas as pd
import requests
from bs4 import BeautifulSoup

SITEMAP_URL = 'https://www.i-musicnetwork.com/sitemap/salesChannel-4b8b064817284071a04cc1a2c7a1d55e-2fbb5fe2e29a4d70aa5854ce7ce3e20b/4b8b064817284071a04cc1a2c7a1d55e-d20bc771d63049b889561b51db39b535-sitemap-www-i-musicnetwork-com-1.xml.gz'
VYSTUPNY_SUBOR = 'imusicnetwork_sklad.csv'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def get_all_product_urls(sitemap_url):
    print(f"Sťahujem sitemapu...")
    try:
        response = requests.get(sitemap_url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        content = response.content
        if content.startswith(b'\x1f\x8b'):
            content = gzip.GzipFile(fileobj=io.BytesIO(content)).read()
        soup = BeautifulSoup(content, 'lxml-xml')
        return [loc.text for loc in soup.find_all('loc') if '/sitemap/' not in loc.text]
    except Exception as e:
        print(f"Chyba sitemapy: {e}")
        return []

def scrape_product_data(url):
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        if res.status_code != 200: return None
        soup = BeautifulSoup(res.content, 'html.parser')
        sku = soup.find('span', class_='product-detail-ordernumber', itemprop='sku')
        if not sku: return None
        delivery = soup.find('p', class_='delivery-information')
        stock = 1 if delivery and 'sofort verfügbar' in delivery.text.lower() else 0
        return {
            'SKU': sku.get_text(strip=True),
            'Nazov': soup.find('h1').get_text(strip=True) if soup.find('h1') else "N/A",
            'Pocet_ks': stock,
            'URL': url
        }
    except:
        return None

if __name__ == "__main__":
    urls = get_all_product_urls(SITEMAP_URL)
    if not urls: exit()
    vysledky = []
    for i, url in enumerate(urls):
        data = scrape_product_data(url)
        if data: vysledky.append(data)
        if (i + 1) % 50 == 0: print(f"Spracované {i+1}/{len(urls)}")
        time.sleep(0.1)

    if vysledky:
        pd.DataFrame(vysledky).to_csv(VYSTUPNY_SUBOR, index=False, encoding='utf-8-sig', sep=';')
        print("Súbor vytvorený.")
