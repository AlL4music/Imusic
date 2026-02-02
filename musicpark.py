"""
Music-Park.sk Scraper
Stiahne produkty z music-park.sk
"""

import re
from bs4 import BeautifulSoup
from base_scraper import BaseScraper, ScraperConfig, extract_number


class ScraperMusicPark(BaseScraper):
    """Scraper pre music-park.sk"""

    def get_sitemap_urls(self):
        """Override - filtrujeme len produktove stranky"""
        urls = super().get_sitemap_urls()
        # Len stranky s /produkt/ v URL
        return [url for url in urls if '/produkt/' in url]

    def parse_product(self, soup: BeautifulSoup, url: str):
        # 1. SKU
        kod = None
        sku_div = soup.find('div', string=re.compile(r'Obj\. kód:'))
        if sku_div:
            kod = sku_div.get_text(strip=True).split(':')[-1].strip().replace('\xa0', '')

        if not kod:
            return None

        # 2. Nazov
        nazov_el = soup.find('h1')
        nazov = nazov_el.get_text(strip=True) if nazov_el else "N/A"

        # 3. Sklad
        stock = 0
        stock_span = soup.find('span', class_='dostupnost')
        if stock_span and 'skladom' in stock_span.get_text().lower():
            stock = extract_number(stock_span.get_text()) or 1

        return {
            'SKU': kod,
            'Nazov': nazov,
            'Pocet_ks': stock
        }


if __name__ == "__main__":
    config = ScraperConfig(
        sitemap_url='https://www.music-park.sk/sitemap.xml',
        output_file='musicpark_sklad.csv',
        max_workers=5,
        url_blacklist=[]  # filtrujeme v get_sitemap_urls
    )

    scraper = ScraperMusicPark(config)
    scraper.run()
