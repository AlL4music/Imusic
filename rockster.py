"""
Rockster.cz Scraper
Stiahne produkty z rockster.cz
Poznamka: Rockster potrebuje pomalsi pristup
"""

import re
from bs4 import BeautifulSoup
from base_scraper import BaseScraper, ScraperConfig, extract_number


class ScraperRockster(BaseScraper):
    """Scraper pre rockster.cz"""

    def parse_product(self, soup: BeautifulSoup, url: str):
        # 1. SKU
        sku_span = soup.find('span', class_='js_kod')
        kod_produktu = sku_span.get_text(strip=True) if sku_span else None

        if not kod_produktu:
            return None

        # 2. Nazov
        nazov_element = soup.find('h1')
        nazov_produktu = nazov_element.get_text(strip=True) if nazov_element else "N/A"

        # 3. Cena
        cena_finalna = "0"
        price_span = soup.find('span', class_='price')
        if price_span:
            cena_text = price_span.get_text(strip=True)
            cena_finalna = cena_text.replace('€', '').replace('\xa0', '').replace(' ', '').strip()

        # 4. Sklad
        skladom_hodnota = 0
        stock_span = soup.find('span', class_='status js_dostupnost')
        if stock_span:
            stock_text = stock_span.get_text(strip=True).lower()
            if 'skladem' in stock_text:
                match = re.search(r'\(>?(\d+)\s*ks\)', stock_text)
                skladom_hodnota = int(match.group(1)) if match else 1

        return {
            'SKU': kod_produktu,
            'Nazov': nazov_produktu,
            'Cena': cena_finalna,
            'Pocet_ks': skladom_hodnota
        }


if __name__ == "__main__":
    config = ScraperConfig(
        sitemap_url='https://www.rockster.cz/sitemap-product-1.xml',
        output_file='rockster_sklad.csv',
        max_workers=5,
        delay=0.2,  # 200ms medzi requestami
        url_blacklist=[]
    )

    scraper = ScraperRockster(config)
    scraper.run()
