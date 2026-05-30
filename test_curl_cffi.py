#!/usr/bin/env python3
"""Test curl_cffi against MDPI Akamai"""
from curl_cffi import requests as curl_req

doi = "10.3390/antiox13030309"
suffix = doi.split('/')[1]

# Test 1: Direct PDF with curl_cffi (Chrome fingerprint)
print("=== curl_cffi to MDPI PDF ===")
try:
    r = curl_req.get(
        f"https://www.mdpi.com/{suffix}/pdf",
        impersonate="chrome131",
        timeout=30
    )
    print(f"Status: {r.status_code}")
    print(f"Size: {len(r.content)}")
    print(f"Is PDF: {b'%PDF' in r.content[:200]}")
except Exception as e:
    print(f"Error: {e}")

# Test 2: Article page
print("\n=== Article page ===")
try:
    r2 = curl_req.get(
        f"https://www.mdpi.com/{suffix}",
        impersonate="chrome131",
        timeout=30
    )
    print(f"Status: {r2.status_code}")
    print(f"Size: {len(r2.content)}")
    if r2.status_code == 200:
        import re
        pdf_links = re.findall(r'href=["\']([^"\']+\.pdf[^"\']*)["\']', r2.text)
        print(f"PDF links: {pdf_links[:5]}")
except Exception as e:
    print(f"Error: {e}")

# Test 3: Try with known URL structure
print("\n=== Known direct URL ===")
try:
    r3 = curl_req.get(
        "https://www.mdpi.com/2076-3921/13/3/309/pdf",
        impersonate="chrome131",
        timeout=30
    )
    print(f"Status: {r3.status_code}")
    print(f"Size: {len(r3.content)}")
    print(f"Is PDF: {b'%PDF' in r3.content[:200]}")
except Exception as e:
    print(f"Error: {e}")
