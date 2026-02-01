"""
Basys.sk Scraper
Stiahne produkty z basys.sk
Poznamka: Basys je citlivy na rychlost, preto pouzivame delay a menej workerov
"""

import os
import re
from bs4 import BeautifulSoup
from base_scraper import BaseScraper, ScraperConfig


class ScraperBasys(BaseScraper):
    """Scraper pre basys.sk"""

    def get_sitemap_urls(self):
        """Override - Basys pouziva lokalny XML subor"""
        local_file = 'sitemap_basys.xml'

        if os.path.exists(local_file):
            self.logger.info(f"Citam lokalny sitemap: {local_file}")
            with open(local_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Extrahuj URL z XML
            urls = re.findall(r'<loc>(https?://[^<]+)</loc>', content)

            # Filter: len .html stranky, nie kategorie
            filtered = [u.strip() for u in urls if u.endswith('.html') and '/c/' not in u]
            self.logger.info(f"Najdenych {len(filtered)} URL")
            return filtered
        else:
            self.logger.warning(f"Lokalny sitemap {local_file} neexistuje, skusam online...")
            return super().get_sitemap_urls()

    def parse_product(self, soup: BeautifulSoup, url: str):
        # 1. Nazov
        nazov_el = soup.find('h1', class_='col-xs-12')
        nazov = nazov_el.get_text(strip=True) if nazov_el else "N/A"

        # 2. SKU
        sku_el = soup.find('span', itemprop='sku')
        sku = sku_el.get_text(strip=True) if sku_el else None

        if not sku:
            return None

        # 3. Sklad (av-7 = na sklade)
        skladom = 1 if soup.find('i', class_='av-7') else 0

        return {
            'SKU': sku,
            'Nazov': nazov,
            'Pocet_ks': skladom
        }


if __name__ == "__main__":
    config = ScraperConfig(
        sitemap_url='https://www.basys.sk/sitemap.xml',  # fallback ak lokalny neexistuje
        output_file='basys_sklad.csv',
        max_workers=5,  # Basys je citlivy
        delay=0.3,      # 300ms medzi requestami
        url_blacklist=['/c/']
    )

    scraper = ScraperBasys(config)
    scraper.run()
