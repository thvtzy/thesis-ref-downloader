#!/usr/bin/env python3
"""Debug MDPI direct download - test cloudscraper on one DOI"""
import cloudscraper, re, logging
logging.disable(logging.CRITICAL)

scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}, delay=3)

doi = "10.3390/antiox13030309"  # Yamauchi 2024 - Antioxidants
suffix = doi.split('/')[1]

# Test 1: Direct PDF URL
url = f"https://www.mdpi.com/{suffix}/pdf"
print(f"=== Testing: {url} ===")
try:
    r = scraper.get(url, timeout=30)
    print(f"Status: {r.status_code}")
    print(f"Size: {len(r.content)}")
    print(f"Is PDF: {b'%PDF' in r.content[:200]}")
    if r.status_code != 200:
        print(f"First 500 chars: {r.text[:500]}")
except Exception as e:
    print(f"Error: {e}")

# Test 2: Article page first, find PDF link
url2 = f"https://www.mdpi.com/{suffix}"
print(f"\n=== Article page: {url2} ===")
try:
    r2 = scraper.get(url2, timeout=30)
    print(f"Status: {r2.status_code}")
    print(f"Size: {len(r2.content)}")
    if r2.status_code == 200:
        pdf_links = re.findall(r'href=["\']([^"\']+\.pdf[^"\']*)["\']', r2.text)
        print(f"PDF links found: {pdf_links[:5]}")
        # Also find any download links
        all_links = re.findall(r'href=["\']([^"\']+)["\']', r2.text)
        pdf_related = [l for l in all_links if 'pdf' in l.lower() or 'download' in l.lower()]
        print(f"PDF/download links: {pdf_related[:10]}")
    else:
        print(f"First 500: {r2.text[:500]}")
except Exception as e:
    print(f"Error: {e}")

# Test 3: Use known MDPI URL structure with journal ID
# antiox13030309 → journal=antioxidants (antiox prefix), volume=13, issue=3, article=309
# So URL should be: https://www.mdpi.com/2076-3921/13/3/309/pdf
url3 = f"https://www.mdpi.com/2076-3921/13/3/309/pdf"
print(f"\n=== Known URL: {url3} ===")
try:
    r3 = scraper.get(url3, timeout=30)
    print(f"Status: {r3.status_code}")
    print(f"Size: {len(r3.content)}")
    print(f"Is PDF: {b'%PDF' in r3.content[:200]}")
except Exception as e:
    print(f"Error: {e}")
