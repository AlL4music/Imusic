"""
Eprodance.cz Scraper
Stiahne produkty z eprodance.cz (Shoptet platforma)
"""

import re
from bs4 import BeautifulSoup
from base_scraper import BaseScraper, ScraperConfig, extract_number


class ScraperEprodance(BaseScraper):
    """Scraper pre eprodance.cz"""

    def parse_product(self, soup: BeautifulSoup, url: str):
        # 1. Nazov (H1)
        nazov_element = soup.find('h1')
        if not nazov_element:
            return None
        nazov_produktu = nazov_element.get_text(strip=True)

        # 2. SKU - Shoptet moze mat viacero miest
        sku_element = (
            soup.find('span', class_='code') or
            soup.find('span', itemprop='sku') or
            soup.find('meta', itemprop='sku')
        )

        kod_produktu = None
        if sku_element:
            kod_produktu = sku_element.get('content') if sku_element.name == 'meta' else sku_element.get_text(strip=True)

        if not kod_produktu:
            return None

        # 3. Sklad
        skladom_hodnota = 0
        stock_span = soup.find('span', class_='availability-amount') or soup.find('span', class_='stock-amount')

        if stock_span:
            skladom_hodnota = extract_number(stock_span.get_text(strip=True))

        return {
            'SKU': kod_produktu,
            'Nazov': nazov_produktu,
            'Pocet_ks': skladom_hodnota
        }


if __name__ == "__main__":
    config = ScraperConfig(
        sitemap_url='https://www.eprodance.cz/sitemap.xml',
        output_file='eprodance_sklad.csv',
        max_workers=10,
        url_blacklist=['/znacka/', '/clanky/', '/blog/', '/vyrobce/', '/kontakt', '/o-nas', '/kosik', '/zakaznik']
    )

    scraper = ScraperEprodance(config)
    scraper.run()
