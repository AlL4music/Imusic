"""
BaseScraper - spolocna trieda pre vsetky scrapers
Riesuje: thread-safety, retry logiku, logging, error handling
"""

import time
import re
import gzip
import io
import logging
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Dict, List, Any
from dataclasses import dataclass

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup


@dataclass
class ScraperConfig:
    """Konfiguracia pre scraper"""
    sitemap_url: str
    output_file: str
    max_workers: int = 10
    timeout: int = 15
    delay: float = 0.0  # delay medzi requestami (pre pomale servery)
    csv_separator: str = ';'
    url_blacklist: List[str] = None  # URL patterny na vynechanie

    def __post_init__(self):
        if self.url_blacklist is None:
            self.url_blacklist = []


class BaseScraper(ABC):
    """
    Zakladna trieda pre web scrapers.

    Pouzitie:
        class MojScraper(BaseScraper):
            def parse_product(self, soup, url):
                # implementuj parsing pre konkretny web
                return {'SKU': ..., 'Nazov': ..., 'Pocet_ks': ...}

        scraper = MojScraper(config)
        scraper.run()
    """

    DEFAULT_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'sk,cs;q=0.9,en;q=0.8',
    }

    def __init__(self, config: ScraperConfig):
        self.config = config
        self.logger = self._setup_logger()
        self.results: List[Dict] = []

    def _setup_logger(self) -> logging.Logger:
        """Nastavi logger pre scraper"""
        logger = logging.getLogger(self.__class__.__name__)
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%H:%M:%S'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    def _create_session(self) -> requests.Session:
        """
        Vytvori session s retry logikou.
        Kazde vlakno by malo mat vlastnu session (thread-safety).
        """
        session = requests.Session()
        session.headers.update(self.DEFAULT_HEADERS)

        # Retry strategia: 3 pokusy s exponential backoff
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,  # 1s, 2s, 4s
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def get_sitemap_urls(self) -> List[str]:
        """Stiahne a spracuje sitemap, vrati zoznam URL produktov"""
        self.logger.info(f"Stahujem sitemap: {self.config.sitemap_url}")

        session = self._create_session()
        try:
            response = session.get(self.config.sitemap_url, timeout=30)
            response.raise_for_status()

            content = response.content

            # Ak je sitemap gzipovana
            if content.startswith(b'\x1f\x8b'):
                content = gzip.GzipFile(fileobj=io.BytesIO(content)).read()

            soup = BeautifulSoup(content, 'lxml-xml')

            all_urls = []
            for url_tag in soup.find_all('url'):
                loc = url_tag.find('loc', recursive=False)
                if loc and loc.text:
                    all_urls.append(loc.text)

            # Ak nie su <url> tagy, skus priamo <loc>
            if not all_urls:
                all_urls = [loc.text for loc in soup.find_all('loc') if loc.text]

            # Filtruj podla blacklistu
            filtered_urls = [
                url for url in all_urls
                if not any(pattern in url for pattern in self.config.url_blacklist)
            ]

            self.logger.info(f"Najdenych {len(filtered_urls)} URL (z {len(all_urls)} celkovo)")
            return filtered_urls

        except requests.RequestException as e:
            self.logger.error(f"Chyba pri stahovani sitemap: {e}")
            return []
        finally:
            session.close()

    @abstractmethod
    def parse_product(self, soup: BeautifulSoup, url: str) -> Optional[Dict[str, Any]]:
        """
        Spracuje HTML stranku produktu a vrati data.

        Args:
            soup: BeautifulSoup objekt s HTML strankou
            url: URL stranky

        Returns:
            Dict s klucmi 'SKU', 'Nazov', 'Pocet_ks' alebo None ak parsing zlyhal
        """
        pass

    def scrape_product(self, url: str, session: requests.Session) -> Optional[Dict]:
        """Stiahne a spracuje jednu produktovu stranku"""
        try:
            if self.config.delay > 0:
                time.sleep(self.config.delay)

            response = session.get(url, timeout=self.config.timeout)

            if response.status_code != 200:
                return None

            response.encoding = response.apparent_encoding or 'utf-8'
            soup = BeautifulSoup(response.content, 'html.parser')

            result = self.parse_product(soup, url)

            if result and result.get('SKU'):
                result['URL'] = url
                return result

        except requests.RequestException as e:
            self.logger.debug(f"Request error pre {url}: {e}")
        except Exception as e:
            self.logger.debug(f"Parse error pre {url}: {e}")

        return None

    def _worker(self, urls: List[str]) -> List[Dict]:
        """Worker funkcia pre jedno vlakno - ma vlastnu session"""
        session = self._create_session()
        results = []

        try:
            for url in urls:
                data = self.scrape_product(url, session)
                if data:
                    results.append(data)
        finally:
            session.close()

        return results

    def run(self) -> pd.DataFrame:
        """Spusti scraper a vrati DataFrame s vysledkami"""
        urls = self.get_sitemap_urls()

        if not urls:
            self.logger.warning("Ziadne URL na spracovanie")
            return pd.DataFrame()

        self.logger.info(f"Spustam scraping {len(urls)} produktov ({self.config.max_workers} vlakien)")
        start_time = time.time()

        # Rozdel URL medzi workery
        chunk_size = max(1, len(urls) // self.config.max_workers)
        url_chunks = [urls[i:i + chunk_size] for i in range(0, len(urls), chunk_size)]

        all_results = []
        processed = 0

        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            futures = {executor.submit(self._worker, chunk): i for i, chunk in enumerate(url_chunks)}

            for future in as_completed(futures):
                try:
                    chunk_results = future.result()
                    all_results.extend(chunk_results)
                    processed += len(url_chunks[futures[future]])

                    self.logger.info(f"Progress: {processed}/{len(urls)} | Najdene: {len(all_results)}")
                except Exception as e:
                    self.logger.error(f"Worker error: {e}")

        self.results = all_results

        # Uloz do CSV
        if all_results:
            df = pd.DataFrame(all_results)
            df.to_csv(
                self.config.output_file,
                index=False,
                encoding='utf-8-sig',
                sep=self.config.csv_separator
            )

            duration = (time.time() - start_time) / 60
            self.logger.info(f"HOTOVO! {len(df)} produktov za {duration:.2f} minut -> {self.config.output_file}")
            return df
        else:
            self.logger.warning("Ziadne produkty neboli najdene")
            return pd.DataFrame()


# === POMOCNE FUNKCIE PRE PARSING ===

def extract_number(text: str) -> int:
    """Extrahuje prve cislo z textu (napr. '15 ks' -> 15)"""
    if not text:
        return 0
    match = re.search(r'(\d+)', text)
    return int(match.group(1)) if match else 0


def is_in_stock(text: str) -> bool:
    """Skontroluje ci text indikuje dostupnost"""
    if not text:
        return False
    text_lower = text.lower()
    positive = ['skladem', 'skladom', 'ano', 'ihned', 'verfügbar', 'in stock', 'available']
    return any(word in text_lower for word in positive)
