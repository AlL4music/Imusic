"""
Alexim.cz Scraper
Stiahne produkty z alexim.cz
"""

import re
from bs4 import BeautifulSoup
from base_scraper import BaseScraper, ScraperConfig


class ScraperAlexim(BaseScraper):
    """Scraper pre alexim.cz"""

    def parse_product(self, soup: BeautifulSoup, url: str):
        # 1. Nazov
        nazov_el = soup.find('h1', class_='product-detail__title')
        nazov = nazov_el.get_text(strip=True) if nazov_el else "N/A"

        # 2. SKU - viacero moznosti kde moze byt
        sku_el = (
            soup.find('strong', string=re.compile(r'^\d+\.\d+$')) or
            soup.find('strong', itemprop='sku') or
            soup.find('span', itemprop='sku')
        )
        sku = sku_el.get_text(strip=True) if sku_el else None

        if not sku:
            return None

        # 3. Sklad
        stock = 1 if soup.find('strong', string=re.compile(r'skladem', re.IGNORECASE)) else 0

        return {
            'SKU': sku,
            'Nazov': nazov,
            'Pocet_ks': stock
        }


if __name__ == "__main__":
    config = ScraperConfig(
        sitemap_url='https://www.alexim.cz/sitemap.xml',
        output_file='alexim_sklad.csv',
        max_workers=15,
        csv_separator=';',  # zjednotene na ;
        url_blacklist=['/c/', '/v/', '/clanky/', '/images/', '/p/', '.jpg', '.png', '.pdf']
    )

    scraper = ScraperAlexim(config)
    scraper.run()
