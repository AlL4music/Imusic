#!/usr/bin/env python3
"""
SEO Health Checker for all4music.sk
Checks both SK and EN language versions for SEO issues.
Outputs a JSON report to reports/seo_report.json
"""

import requests
import json
import re
import os
import sys
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

SITE_URL = os.environ.get('SITE_URL', 'https://new.all4music.sk')
# Pages to check - add more as needed
CHECK_PATHS = [
    '/',
    '/index.php?route=common/home',
    '/index.php?route=product/category',
]
# Try to discover language URLs from the homepage
LANG_CODES = ['sk', 'en']

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'sk,en;q=0.9',
}

session = requests.Session()
session.headers.update(HEADERS)


def fetch_page(url, timeout=15):
    """Fetch a page and return (response, soup) or (None, None)."""
    try:
        resp = session.get(url, timeout=timeout, allow_redirects=True)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'lxml')
            return resp, soup
        return resp, None
    except Exception as e:
        print(f"  Error fetching {url}: {e}")
        return None, None


def check_meta_tags(soup, url):
    """Check essential meta tags on a page."""
    issues = []
    info = {}

    # Title
    title_tag = soup.find('title')
    title = title_tag.get_text(strip=True) if title_tag else None
    info['title'] = title
    if not title:
        issues.append({'severity': 'error', 'msg': 'Missing <title> tag'})
    elif len(title) < 10:
        issues.append({'severity': 'warning', 'msg': f'Title too short ({len(title)} chars): "{title}"'})
    elif len(title) > 70:
        issues.append({'severity': 'warning', 'msg': f'Title too long ({len(title)} chars, recommended <70)'})

    # Meta description
    desc_tag = soup.find('meta', attrs={'name': 'description'})
    desc = desc_tag.get('content', '').strip() if desc_tag else None
    info['meta_description'] = desc
    if not desc:
        issues.append({'severity': 'error', 'msg': 'Missing meta description'})
    elif len(desc) < 50:
        issues.append({'severity': 'warning', 'msg': f'Meta description too short ({len(desc)} chars)'})
    elif len(desc) > 160:
        issues.append({'severity': 'warning', 'msg': f'Meta description too long ({len(desc)} chars, recommended <160)'})

    # Canonical
    canonical = soup.find('link', attrs={'rel': 'canonical'})
    info['canonical'] = canonical.get('href') if canonical else None
    if not canonical:
        issues.append({'severity': 'warning', 'msg': 'Missing canonical tag'})

    # HTML lang attribute
    html_tag = soup.find('html')
    lang = html_tag.get('lang') if html_tag else None
    info['html_lang'] = lang
    if not lang:
        issues.append({'severity': 'error', 'msg': 'Missing lang attribute on <html> tag'})

    # Viewport
    viewport = soup.find('meta', attrs={'name': 'viewport'})
    info['has_viewport'] = viewport is not None
    if not viewport:
        issues.append({'severity': 'warning', 'msg': 'Missing viewport meta tag (mobile-friendliness)'})

    # Open Graph
    og_title = soup.find('meta', attrs={'property': 'og:title'})
    og_desc = soup.find('meta', attrs={'property': 'og:description'})
    og_image = soup.find('meta', attrs={'property': 'og:image'})
    info['og_title'] = og_title.get('content') if og_title else None
    info['og_description'] = og_desc.get('content') if og_desc else None
    info['og_image'] = og_image.get('content') if og_image else None
    if not og_title:
        issues.append({'severity': 'info', 'msg': 'Missing og:title (Open Graph for social sharing)'})
    if not og_image:
        issues.append({'severity': 'info', 'msg': 'Missing og:image (Open Graph image for social sharing)'})

    return info, issues


def check_hreflang(soup, url):
    """Check hreflang tags for multilingual SEO."""
    issues = []
    info = {}

    hreflangs = soup.find_all('link', attrs={'rel': 'alternate', 'hreflang': True})
    info['hreflang_tags'] = [
        {'lang': tag.get('hreflang'), 'href': tag.get('href')}
        for tag in hreflangs
    ]

    if not hreflangs:
        issues.append({
            'severity': 'error',
            'msg': 'No hreflang tags found. Google cannot distinguish SK/EN versions. '
                   'Add <link rel="alternate" hreflang="sk" href="..."> and hreflang="en" for each page.'
        })
    else:
        langs_found = [tag.get('hreflang') for tag in hreflangs]
        if 'sk' not in langs_found:
            issues.append({'severity': 'error', 'msg': 'Missing hreflang="sk" tag'})
        if 'en' not in langs_found:
            issues.append({'severity': 'error', 'msg': 'Missing hreflang="en" tag'})
        if 'x-default' not in langs_found:
            issues.append({'severity': 'warning', 'msg': 'Missing hreflang="x-default" (recommended as fallback)'})

        # Check that hreflang URLs are absolute
        for tag in hreflangs:
            href = tag.get('href', '')
            if href and not href.startswith('http'):
                issues.append({'severity': 'error', 'msg': f'hreflang URL must be absolute: {href}'})

    return info, issues


def check_headings(soup, url):
    """Check heading structure."""
    issues = []
    info = {}

    h1s = soup.find_all('h1')
    info['h1_count'] = len(h1s)
    info['h1_texts'] = [h.get_text(strip=True)[:100] for h in h1s]

    if len(h1s) == 0:
        issues.append({'severity': 'error', 'msg': 'No H1 tag found on page'})
    elif len(h1s) > 1:
        issues.append({'severity': 'warning', 'msg': f'Multiple H1 tags found ({len(h1s)}). Use only one H1 per page.'})

    h2s = soup.find_all('h2')
    info['h2_count'] = len(h2s)

    return info, issues


def check_images(soup, url):
    """Check images for alt tags."""
    issues = []
    info = {}

    images = soup.find_all('img')
    missing_alt = [img.get('src', '')[:80] for img in images if not img.get('alt')]
    info['total_images'] = len(images)
    info['missing_alt_count'] = len(missing_alt)

    if missing_alt:
        issues.append({
            'severity': 'warning',
            'msg': f'{len(missing_alt)} of {len(images)} images missing alt text'
        })

    return info, issues


def check_structured_data(soup, url):
    """Check for JSON-LD structured data."""
    issues = []
    info = {}

    ld_scripts = soup.find_all('script', attrs={'type': 'application/ld+json'})
    info['json_ld_count'] = len(ld_scripts)
    info['json_ld_types'] = []

    for script in ld_scripts:
        try:
            data = json.loads(script.string)
            if isinstance(data, dict):
                info['json_ld_types'].append(data.get('@type', 'unknown'))
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        info['json_ld_types'].append(item.get('@type', 'unknown'))
        except (json.JSONDecodeError, TypeError):
            pass

    if not ld_scripts:
        issues.append({
            'severity': 'warning',
            'msg': 'No structured data (JSON-LD) found. '
                   'Add Organization, Product, or BreadcrumbList schema for better Google results.'
        })

    return info, issues


def check_robots_txt(base_url):
    """Check robots.txt."""
    issues = []
    info = {}

    resp, _ = fetch_page(f'{base_url}/robots.txt')
    if resp and resp.status_code == 200:
        content = resp.text
        info['exists'] = True
        info['content'] = content[:1000]
        info['has_sitemap'] = 'sitemap' in content.lower()
        if not info['has_sitemap']:
            issues.append({'severity': 'warning', 'msg': 'robots.txt does not reference a Sitemap'})
        if 'disallow: /' in content.lower() and 'disallow: /\n' not in content.lower():
            issues.append({'severity': 'error', 'msg': 'robots.txt may be blocking all crawlers'})
    else:
        info['exists'] = False
        issues.append({'severity': 'warning', 'msg': 'No robots.txt found'})

    return info, issues


def check_sitemap(base_url):
    """Check sitemap.xml."""
    issues = []
    info = {}

    sitemap_urls = [
        f'{base_url}/sitemap.xml',
        f'{base_url}/index.php?route=extension/feed/google_sitemap',
    ]

    found = False
    for sitemap_url in sitemap_urls:
        resp, soup = fetch_page(sitemap_url)
        if resp and resp.status_code == 200 and resp.text.strip():
            found = True
            info['url'] = sitemap_url
            info['size_bytes'] = len(resp.text)

            # Count URLs in sitemap
            url_count = resp.text.count('<loc>')
            info['url_count'] = url_count
            if url_count == 0:
                issues.append({'severity': 'error', 'msg': f'Sitemap at {sitemap_url} contains 0 URLs'})
            else:
                print(f"  Sitemap found: {sitemap_url} ({url_count} URLs)")

            # Check for language variants in sitemap
            has_xhtml_link = 'xhtml:link' in resp.text or 'hreflang' in resp.text
            info['has_hreflang_in_sitemap'] = has_xhtml_link
            if not has_xhtml_link:
                issues.append({
                    'severity': 'warning',
                    'msg': 'Sitemap does not include hreflang annotations. '
                           'For multilingual sites, add <xhtml:link> entries for each language variant.'
                })
            break

    if not found:
        info['url'] = None
        issues.append({'severity': 'error', 'msg': 'No sitemap.xml found'})

    return info, issues


def check_page_speed_basics(soup, resp, url):
    """Basic checks that affect page speed / Core Web Vitals."""
    issues = []
    info = {}

    html = resp.text if resp else ''

    # Check for render-blocking resources
    sync_scripts = soup.find_all('script', attrs={'src': True})
    async_defer_count = sum(1 for s in sync_scripts if s.get('async') or s.get('defer'))
    info['total_scripts'] = len(sync_scripts)
    info['async_defer_scripts'] = async_defer_count

    blocking = len(sync_scripts) - async_defer_count
    if blocking > 3:
        issues.append({
            'severity': 'warning',
            'msg': f'{blocking} render-blocking scripts found. Consider adding async/defer.'
        })

    # Check page size
    info['page_size_kb'] = round(len(html) / 1024, 1)
    if len(html) > 500000:
        issues.append({
            'severity': 'warning',
            'msg': f'Page HTML is {info["page_size_kb"]}KB (over 500KB). Consider reducing page size.'
        })

    # HTTPS check
    info['is_https'] = url.startswith('https')
    if not info['is_https']:
        issues.append({'severity': 'error', 'msg': 'Page not served over HTTPS'})

    return info, issues


def check_language_separation(base_url):
    """Try to detect how SK/EN versions are separated and check for duplicate content issues."""
    issues = []
    info = {}

    # Try common OpenCart language URL patterns
    patterns = [
        (f'{base_url}/index.php?route=common/home&language=sk', 'query_param'),
        (f'{base_url}/index.php?route=common/home&language=en-gb', 'query_param'),
        (f'{base_url}/sk/', 'path_prefix'),
        (f'{base_url}/en/', 'path_prefix'),
    ]

    found_langs = {}
    for test_url, pattern_type in patterns:
        resp, soup = fetch_page(test_url)
        if resp and resp.status_code == 200 and soup:
            lang_code = 'sk' if 'sk' in test_url else 'en'
            html_tag = soup.find('html')
            actual_lang = html_tag.get('lang', '') if html_tag else ''
            title = soup.find('title')
            title_text = title.get_text(strip=True) if title else ''
            found_langs[lang_code] = {
                'url': test_url,
                'pattern': pattern_type,
                'html_lang': actual_lang,
                'title': title_text[:80]
            }

    info['language_versions'] = found_langs

    if len(found_langs) >= 2:
        # Check if titles are different (translated) or same (duplicate content)
        titles = [v['title'] for v in found_langs.values()]
        if len(set(titles)) == 1 and titles[0]:
            issues.append({
                'severity': 'warning',
                'msg': f'SK and EN pages have identical titles ("{titles[0]}"). '
                       'Titles should be translated for each language version.'
            })

        # Check html lang attributes
        for lang, data in found_langs.items():
            if not data['html_lang']:
                issues.append({
                    'severity': 'error',
                    'msg': f'{lang.upper()} version missing html lang attribute at {data["url"]}'
                })
            elif lang not in data['html_lang'].lower():
                issues.append({
                    'severity': 'warning',
                    'msg': f'{lang.upper()} version has html lang="{data["html_lang"]}" (expected "{lang}")'
                })
    elif len(found_langs) == 1:
        issues.append({
            'severity': 'warning',
            'msg': 'Only one language version detected. Could not find the other language.'
        })
    else:
        issues.append({
            'severity': 'info',
            'msg': 'Could not auto-detect language URL patterns. Check manually.'
        })

    return info, issues


def run_checks():
    """Run all SEO checks and return report."""
    report = {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'site_url': SITE_URL,
        'pages': [],
        'global_checks': {},
        'summary': {'errors': 0, 'warnings': 0, 'info': 0, 'passed': 0}
    }

    # Global checks
    print(f"Checking {SITE_URL}...")

    print("  Checking robots.txt...")
    robots_info, robots_issues = check_robots_txt(SITE_URL)
    report['global_checks']['robots_txt'] = {'info': robots_info, 'issues': robots_issues}

    print("  Checking sitemap...")
    sitemap_info, sitemap_issues = check_sitemap(SITE_URL)
    report['global_checks']['sitemap'] = {'info': sitemap_info, 'issues': sitemap_issues}

    print("  Checking language separation...")
    lang_info, lang_issues = check_language_separation(SITE_URL)
    report['global_checks']['language_separation'] = {'info': lang_info, 'issues': lang_issues}

    # Per-page checks
    for path in CHECK_PATHS:
        url = f'{SITE_URL}{path}'
        print(f"  Checking page: {url}")

        resp, soup = fetch_page(url)
        if not soup:
            report['pages'].append({
                'url': url,
                'status': resp.status_code if resp else 'error',
                'issues': [{'severity': 'error', 'msg': f'Could not fetch page (status: {resp.status_code if resp else "connection error"})'}]
            })
            continue

        page_report = {
            'url': resp.url,  # Use final URL after redirects
            'status': resp.status_code,
            'checks': {},
            'issues': []
        }

        # Run all page-level checks
        for check_name, check_fn in [
            ('meta_tags', check_meta_tags),
            ('hreflang', check_hreflang),
            ('headings', check_headings),
            ('images', check_images),
            ('structured_data', check_structured_data),
        ]:
            info, issues = check_fn(soup, url)
            page_report['checks'][check_name] = info
            page_report['issues'].extend(issues)

        speed_info, speed_issues = check_page_speed_basics(soup, resp, url)
        page_report['checks']['page_speed'] = speed_info
        page_report['issues'].extend(speed_issues)

        report['pages'].append(page_report)

    # Count totals
    all_issues = []
    for section in report['global_checks'].values():
        all_issues.extend(section.get('issues', []))
    for page in report['pages']:
        all_issues.extend(page.get('issues', []))

    report['summary']['errors'] = sum(1 for i in all_issues if i['severity'] == 'error')
    report['summary']['warnings'] = sum(1 for i in all_issues if i['severity'] == 'warning')
    report['summary']['info'] = sum(1 for i in all_issues if i['severity'] == 'info')
    report['summary']['total_checks'] = len(all_issues)

    return report


def print_report(report):
    """Print a human-readable summary."""
    s = report['summary']
    print(f"\n{'='*60}")
    print(f"SEO Health Report for {report['site_url']}")
    print(f"{'='*60}")
    print(f"Errors: {s['errors']}  |  Warnings: {s['warnings']}  |  Info: {s['info']}")
    print(f"{'='*60}")

    # Global issues
    for name, section in report['global_checks'].items():
        if section['issues']:
            print(f"\n[{name.upper()}]")
            for issue in section['issues']:
                icon = {'error': 'X', 'warning': '!', 'info': 'i'}[issue['severity']]
                print(f"  [{icon}] {issue['msg']}")

    # Per-page issues
    for page in report['pages']:
        if page.get('issues'):
            print(f"\n[PAGE: {page['url']}]")
            for issue in page['issues']:
                icon = {'error': 'X', 'warning': '!', 'info': 'i'}[issue['severity']]
                print(f"  [{icon}] {issue['msg']}")

    print(f"\n{'='*60}")


if __name__ == '__main__':
    report = run_checks()
    print_report(report)

    # Save JSON report
    os.makedirs('reports', exist_ok=True)
    report_path = 'reports/seo_report.json'
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nFull report saved to {report_path}")

    # Exit with error code if critical issues found
    if report['summary']['errors'] > 0:
        sys.exit(1)
