"""
3DMX.cz Scraper
Stiahne produkty z 3dmx.cz
"""

import re
from bs4 import BeautifulSoup
from base_scraper import BaseScraper, ScraperConfig, extract_number, is_in_stock


class Scraper3DMX(BaseScraper):
    """Scraper pre 3dmx.cz"""

    def parse_product(self, soup: BeautifulSoup, url: str):
        # 1. SKU - kod produktu
        sku_td = soup.find('td', class_='td_katalog_detail_polozka')
        kod_produktu = sku_td.get_text(strip=True) if sku_td else None

        if not kod_produktu:
            return None

        # 2. Nazov
        nazov_element = soup.find('h1')
        nazov_produktu = nazov_element.get_text(strip=True) if nazov_element else "N/A"

        # 3. Sklad
        skladom_hodnota = 0
        stock_span = soup.find('span', class_='skladem')
        if stock_span:
            stock_text = stock_span.get_text(strip=True)
            skladom_hodnota = extract_number(stock_text)
            if skladom_hodnota == 0 and is_in_stock(stock_text):
                skladom_hodnota = 1

        return {
            'SKU': kod_produktu,
            'Nazov': nazov_produktu,
            'Pocet_ks': skladom_hodnota
        }


if __name__ == "__main__":
    config = ScraperConfig(
        sitemap_url='https://www.3dmx.cz/sitemap/sitemap_cs.xml',
        output_file='3dmx_sklad.csv',
        max_workers=15,
        url_blacklist=['/c/', '/vyr/']  # kategorie a vyrobcovia
    )

    scraper = Scraper3DMX(config)
    scraper.run()
