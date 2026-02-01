"""
MusicTrade.cz Scraper
Stiahne produkty z musictrade.cz
Poznamka: Extrahuje data z JavaScript dataLayer objektu (robustnejsie ako HTML parsing)
"""

import re
import json
from bs4 import BeautifulSoup
from base_scraper import BaseScraper, ScraperConfig


class ScraperMusicTrade(BaseScraper):
    """Scraper pre musictrade.cz"""

    def parse_product(self, soup: BeautifulSoup, url: str):
        # Hladame dataLayer.push v scriptoch
        scripts = soup.find_all('script')
        data_script = next(
            (s.string for s in scripts if s.string and 'dataLayer.push' in s.string and '"product":' in s.string),
            None
        )

        if not data_script:
            return None

        # Extrahuj JSON produkt z dataLayer
        match = re.search(r'"product":\s*({.*?"priceWithVat":.*?})\s*,', data_script, re.DOTALL)
        if not match:
            return None

        try:
            product_data = json.loads(match.group(1).replace(r'\/', '/'))
        except json.JSONDecodeError:
            return None

        # SKU
        sku = product_data.get('code')
        if not sku:
            return None

        # Nazov
        nazov = product_data.get('name', 'N/A')

        # Sklad
        skladom_hodnota = 0
        if product_data.get('codes'):
            quantity_str = product_data['codes'][0].get('quantity')
            if quantity_str:
                quantity_clean = str(quantity_str).replace('>', '').strip()
                try:
                    skladom_hodnota = int(quantity_clean)
                except ValueError:
                    skladom_hodnota = 1

        return {
            'SKU': sku,
            'Nazov': nazov,
            'Pocet_ks': skladom_hodnota
        }


if __name__ == "__main__":
    config = ScraperConfig(
        sitemap_url='https://www.musictrade.cz/sitemap.xml',
        output_file='musictrade_sklad.csv',
        max_workers=20,
        url_blacklist=['/znacka/', '/kategorie/']
    )

    scraper = ScraperMusicTrade(config)
    scraper.run()
