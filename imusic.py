"""
i-MusicNetwork.com Scraper
Stiahne produkty z i-musicnetwork.com
Poznamka: Pouziva gzip sitemap
"""

from bs4 import BeautifulSoup
from base_scraper import BaseScraper, ScraperConfig


class ScraperIMusicNetwork(BaseScraper):
    """Scraper pre i-musicnetwork.com"""

    def get_sitemap_urls(self):
        """Override - filtruj sitemap URL"""
        urls = super().get_sitemap_urls()
        return [url for url in urls if '/sitemap/' not in url]

    def parse_product(self, soup: BeautifulSoup, url: str):
        # 1. SKU
        sku = soup.find('span', class_='product-detail-ordernumber', itemprop='sku')
        if not sku:
            return None

        sku_text = sku.get_text(strip=True)

        # 2. Nazov
        nazov = soup.find('h1')
        nazov_text = nazov.get_text(strip=True) if nazov else "N/A"

        # 3. Sklad (nemecky "sofort verfügbar" = ihned dostupne)
        delivery = soup.find('p', class_='delivery-information')
        stock = 1 if delivery and 'sofort verfügbar' in delivery.text.lower() else 0

        return {
            'SKU': sku_text,
            'Nazov': nazov_text,
            'Pocet_ks': stock
        }


if __name__ == "__main__":
    config = ScraperConfig(
        sitemap_url='https://www.i-musicnetwork.com/sitemap/salesChannel-4b8b064817284071a04cc1a2c7a1d55e-2fbb5fe2e29a4d70aa5854ce7ce3e20b/4b8b064817284071a04cc1a2c7a1d55e-d20bc771d63049b889561b51db39b535-sitemap-www-i-musicnetwork-com-1.xml.gz',
        output_file='imusicnetwork_sklad.csv',
        max_workers=10,
        delay=0.1,
        url_blacklist=[]
    )

    scraper = ScraperIMusicNetwork(config)
    scraper.run()
