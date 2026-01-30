#!/usr/bin/env python3
"""
ESP Guitar Scraper
==================
Scrapes product data from espguitars.com and generates HTML descriptions
for eMagicone import.

Usage:
    python esp_guitar_scraper.py input.csv output.csv

Requirements:
    pip install requests beautifulsoup4 pandas tqdm
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import csv
import time
import argparse
from tqdm import tqdm
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# HTML Template
HTML_TEMPLATE = '''<style>
.product-description-container{{font-family:'Roboto',sans-serif;color:#374151}}.product-description-container h3,.product-description-container h4{{font-family:'Barlow',sans-serif;font-weight:900;letter-spacing:-.025em;color:#111827}}.product-description-container ul{{list-style-type:disc;margin-left:1.5rem;margin-bottom:1rem;padding-left:1rem}}.product-description-container li{{margin-bottom:.25rem}}.product-description-container .prose{{line-height:1.75}}.features-3col-section{{text-align:center;padding:2rem 0}}.features-3col-section .main-image img{{border-radius:.75rem;box-shadow:0 10px 15px -3px rgba(0,0,0,.1);width:100%;max-width:800px;margin:0 auto 2rem auto}}.features-3col-section .main-text{{max-width:800px;margin:0 auto 3rem auto}}.features-3col-section .main-text h3{{font-size:2.25rem;margin-bottom:1rem}}.features-3col-section .columns-container{{display:grid;gap:2rem;max-width:1200px;margin:0 auto}}.features-3col-section .columns-container.cols-3{{grid-template-columns:repeat(3,1fr)}}.features-3col-section .feature-item{{text-align:left}}.features-3col-section .feature-item svg{{width:48px;height:48px;margin-bottom:1rem;color:#e7284d}}.features-3col-section .feature-item h4{{font-size:1.25rem;font-weight:700;margin-bottom:.5rem}}.desc-section{{display:grid;grid-template-columns:1fr 1fr;gap:2rem;align-items:center;margin-bottom:2rem}}.desc-section.image-layout-left .desc-image{{order:1}}.desc-section.image-layout-left .desc-text{{order:2}}.desc-section.image-layout-right .desc-image{{order:2}}.desc-section.image-layout-right .desc-text{{order:1}}.desc-image{{border-radius:.75rem;overflow:hidden;box-shadow:0 10px 15px -3px rgba(0,0,0,.1);background-color:#f9fafb}}.desc-image img{{width:100%;height:100%;display:block;object-fit:contain}}.desc-text h3{{font-size:1.875rem;margin-bottom:1rem}}@media(max-width:768px){{.desc-section{{grid-template-columns:1fr}}.features-3col-section .columns-container.cols-3{{grid-template-columns:1fr}}}}
</style>
<div class="product-description-container">
<section class="features-3col-section">
    <div class="main-text">
        <h3>{brand} {model}</h3>
        <div class="prose max-w-none"><b>{color}</b></div>
    </div>
    <div class="main-image"><img src="{img_1}" alt="{brand} {model} {color}" loading="lazy"></div>
    <div class="columns-container cols-3">
        <div class="feature-item">
            <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"></path><path d="m9 12 2 2 4-4"></path></svg> 
            <h4>Professional Quality</h4>
            <div class="prose max-w-none">{desc_1}</div>
        </div>
        <div class="feature-item">
            <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"></path><path d="m9 12 2 2 4-4"></path></svg> 
            <h4>Premium Construction</h4>
            <div class="prose max-w-none">{desc_2}</div>
        </div>
        <div class="feature-item">
            <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"></path><path d="m9 12 2 2 4-4"></path></svg> 
            <h4>{pickup_title}</h4>
            <div class="prose max-w-none">{desc_3}</div>
        </div>
    </div>
</section>
<section class="desc-section image-layout-left">
    <div class="desc-image fit-contain" style="height:450px;max-height:450px;">
        <img src="{img_2}" alt="{brand} {model}" loading="lazy">
    </div>
    <div class="desc-text"><h3>Specifications</h3><div class="prose max-w-none"><ul>
{specs_1}
</ul></div></div>
</section>
<section class="desc-section image-layout-right">
    <div class="desc-image fit-contain" style="height:450px;max-height:450px;">
        <img src="{img_3}" alt="{brand} {model}" loading="lazy">
    </div>
    <div class="desc-text"><h3>Electronics &amp; Hardware</h3><div class="prose max-w-none"><ul>
{specs_2}
</ul></div></div>
</section>
</div>'''


class ESPScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self.base_url = "https://www.espguitars.com"
    
    def search_product(self, search_term):
        """Search for a product on ESP website"""
        try:
            url = f"{self.base_url}/search?q={requests.utils.quote(search_term)}&type=products"
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Find product links
            for a in soup.find_all('a', href=True):
                href = a['href']
                if '/products/' in href and not href.endswith('/products') and 'search' not in href:
                    if not href.startswith('http'):
                        href = self.base_url + href
                    return href
            
            return None
        except Exception as e:
            logger.error(f"Search error for '{search_term}': {e}")
            return None
    
    def fetch_product_page(self, url):
        """Fetch product page HTML"""
        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            logger.error(f"Fetch error for '{url}': {e}")
            return None
    
    def parse_product_page(self, html, brand, original_name):
        """Parse product page and extract data"""
        if not html:
            return None
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract images
        img_pattern = r'product_images/(\d{3}/\d{3}/\d{3})/original\.png'
        matches = re.findall(img_pattern, html)
        unique_ids = list(dict.fromkeys(matches))
        
        img_urls = [f"https://cdn.connectsites.net/user_files/esp/product_images/{img_id}/original.png" 
                    for img_id in unique_ids[:3]]
        
        while len(img_urls) < 3:
            img_urls.append(img_urls[0] if img_urls else "")
        
        # Extract title and color
        h1 = soup.find('h1')
        h2 = soup.find('h2')
        
        model = h1.text.strip() if h1 else self._extract_model(original_name)
        color = h2.text.strip() if h2 else ""
        
        # Extract specs
        specs = self._extract_specs(html)
        
        # Generate HTML
        html_desc = self._generate_html(brand, model, color, img_urls, specs)
        
        return {
            'model': model,
            'color': color,
            'images': img_urls,
            'specs': specs,
            'html': html_desc
        }
    
    def _extract_model(self, original_name):
        """Extract model from original product name"""
        parts = original_name.split()
        if len(parts) > 1:
            return parts[1]
        return original_name
    
    def _extract_specs(self, html):
        """Extract specifications from HTML"""
        specs = {}
        spec_keys = ['Construction', 'Scale', 'Body', 'Top', 'Neck', 'Fingerboard', 
                     'Fingerboard Radius', 'Finish', 'Nut Width', 'Nut Type', 
                     'Neck Contour', 'Frets/Type', 'Hardware Color', 'Strap Button', 
                     'Tuners', 'Bridge', 'Bridge PU', 'Neck PU', 'Electronics',
                     'Electronics Layout', 'Strings', 'Case']
        
        for key in spec_keys:
            pattern = rf'{re.escape(key)}\s+([^\n<]+?)(?:\n|<|$)'
            match = re.search(pattern, html)
            if match:
                value = match.group(1).strip()
                value = re.sub(r'\[.*?\].*', '', value).strip()
                value = re.sub(r'\s+', ' ', value)
                if value and len(value) < 150:
                    specs[key] = value
        
        return specs
    
    def _generate_html(self, brand, model, color, img_urls, specs):
        """Generate HTML description"""
        # Specs groups
        spec_group_1 = ['Construction', 'Scale', 'Body', 'Top', 'Neck', 'Fingerboard', 
                        'Fingerboard Radius', 'Finish', 'Nut Width', 'Nut Type', 
                        'Neck Contour', 'Frets/Type', 'Hardware Color']
        spec_group_2 = ['Strap Button', 'Tuners', 'Bridge', 'Bridge PU', 'Neck PU', 
                        'Electronics', 'Electronics Layout', 'Strings', 'Case']
        
        specs_1 = '\n'.join([f'<li>{k} - {specs[k]}</li>' for k in spec_group_1 if k in specs])
        specs_2 = '\n'.join([f'<li>{k} - {specs[k]}</li>' for k in spec_group_2 if k in specs])
        
        # Pickup title
        bridge_pu = specs.get('Bridge PU', '')
        if 'EMG' in bridge_pu:
            pickup_title = "Active EMG Pickups"
        elif 'Seymour' in bridge_pu or 'Duncan' in bridge_pu:
            pickup_title = "Seymour Duncan Pickups"
        elif 'Fishman' in bridge_pu:
            pickup_title = "Fishman Fluence Pickups"
        elif 'DiMarzio' in bridge_pu:
            pickup_title = "DiMarzio Pickups"
        else:
            pickup_title = "Premium Pickups"
        
        # Descriptions
        construction = specs.get('Construction', 'set-neck').lower()
        body = specs.get('Body', 'mahogany').lower()
        neck = specs.get('Neck', 'mahogany').lower()
        fingerboard = specs.get('Fingerboard', 'ebony')
        scale = specs.get('Scale', '24.75"')
        neck_contour = specs.get('Neck Contour', 'Thin U')
        
        desc_1 = f"Guitars in the {brand} {model} Series are designed to offer the tone, feel, looks, and quality that working professional musicians need in an instrument, along with the pricing that typical musicians can still afford."
        desc_2 = f"The {model} offers {construction} construction with a {body} body, {neck} neck and {fingerboard} fingerboard. The {scale} scale length and {neck_contour} neck profile provide exceptional playability."
        
        neck_pu = specs.get('Neck PU', '')
        hardware = specs.get('Hardware Color', 'chrome')
        tuners = specs.get('Tuners', 'tuners')
        bridge = specs.get('Bridge', 'bridge')
        
        if neck_pu and bridge_pu:
            desc_3 = f"Equipped with {bridge_pu} (bridge) and {neck_pu} (neck) pickups for powerful, articulate tone. {hardware} hardware, {bridge} and {tuners} complete this professional instrument."
        elif bridge_pu:
            desc_3 = f"Equipped with {bridge_pu} pickup for powerful, articulate tone. {hardware} hardware, {bridge} and {tuners} complete this professional instrument."
        else:
            desc_3 = f"Features {hardware} hardware, {bridge} and {tuners} for professional performance and reliability."
        
        return HTML_TEMPLATE.format(
            brand=brand,
            model=model,
            color=color,
            img_1=img_urls[0],
            img_2=img_urls[1],
            img_3=img_urls[2],
            desc_1=desc_1,
            desc_2=desc_2,
            desc_3=desc_3,
            pickup_title=pickup_title,
            specs_1=specs_1,
            specs_2=specs_2,
        )
    
    def process_product(self, sku, brand, original_name):
        """Process a single product"""
        # Create search term from original name
        search_term = original_name.replace(brand, '').strip()
        # Remove common suffixes
        for suffix in ['Series Guitars', 'Guitars', 'Series']:
            search_term = search_term.replace(suffix, '').strip()
        
        logger.info(f"Processing: {original_name} -> searching: {search_term}")
        
        # Search for product
        product_url = self.search_product(search_term)
        if not product_url:
            logger.warning(f"Not found: {original_name}")
            return None
        
        # Fetch page
        html = self.fetch_product_page(product_url)
        if not html:
            return None
        
        # Parse
        result = self.parse_product_page(html, brand, original_name)
        if not result:
            return None
        
        return {
            'SKU': sku,
            'Brand': brand,
            'Model': result['model'],
            'Color': result['color'],
            'Image_1': result['images'][0],
            'Image_2': result['images'][1],
            'Image_3': result['images'][2],
            'HTML_Description': result['html'],
            'ESP_URL': product_url
        }


def filter_guitars(df):
    """Filter only guitars from the CSV (exclude basses, cases, accessories)"""
    # Exclude non-guitars
    exclude_patterns = [
        'Case', 'CASE', 'Bag', 'BAG', 'GIG', 'Picks', 'Pick', 'Logo', 
        'T Shirt', 'Strap', 'Bass', 'BASS', 'FL-', 'STREAM-', 'B-20', 
        'B-10', 'SURVEYOR', 'Form Fit', 'Tombstone', 'Set A', 'Preamp',
        'MM-04', 'Booster', 'AP-', 'Basses'
    ]
    
    pattern = '|'.join(exclude_patterns)
    df = df[~df['Name'].str.contains(pattern, case=False, na=False)]
    
    return df


def extract_brand(name):
    """Extract brand from product name"""
    if name.startswith('ESP '):
        return 'ESP'
    elif name.startswith('E-II '):
        return 'E-II'
    elif name.startswith('LTD '):
        return 'LTD'
    return 'LTD'


def main():
    parser = argparse.ArgumentParser(description='ESP Guitar Scraper')
    parser.add_argument('input_csv', help='Input CSV file with products')
    parser.add_argument('output_csv', help='Output CSV file')
    parser.add_argument('--limit', type=int, default=0, help='Limit number of products (0 = all)')
    parser.add_argument('--delay', type=float, default=1.0, help='Delay between requests in seconds')
    args = parser.parse_args()
    
    # Load input CSV
    logger.info(f"Loading {args.input_csv}...")
    df = pd.read_csv(args.input_csv)
    
    # Filter guitars
    df = filter_guitars(df)
    logger.info(f"Found {len(df)} guitars to process")
    
    if args.limit > 0:
        df = df.head(args.limit)
        logger.info(f"Limited to {args.limit} products")
    
    # Process
    scraper = ESPScraper()
    results = []
    failed = []
    
    for idx, row in tqdm(df.iterrows(), total=len(df), desc="Scraping"):
        sku = str(row['SKU'])
        original_name = row['Name']
        brand = extract_brand(original_name)
        
        result = scraper.process_product(sku, brand, original_name)
        
        if result:
            results.append(result)
        else:
            failed.append({'SKU': sku, 'Name': original_name})
        
        time.sleep(args.delay)
    
    # Save results
    if results:
        output_df = pd.DataFrame(results)
        output_df.to_csv(args.output_csv, index=False, quoting=csv.QUOTE_ALL)
        logger.info(f"Saved {len(results)} products to {args.output_csv}")
    
    # Save failed
    if failed:
        failed_file = args.output_csv.replace('.csv', '_failed.csv')
        pd.DataFrame(failed).to_csv(failed_file, index=False)
        logger.info(f"Saved {len(failed)} failed products to {failed_file}")
    
    logger.info(f"Done! Success: {len(results)}, Failed: {len(failed)}")


if __name__ == '__main__':
    main()
