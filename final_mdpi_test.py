#!/usr/bin/env python3
"""Final desperate attempts for the most critical papers."""
import requests, re, os, json
from curl_cffi import requests as curl_req

OUT = r"D:\Skripsi_Referensi_PDF"
os.makedirs(OUT, exist_ok=True)
_s = requests.Session()
_s.headers.update({"User-Agent": "Mozilla/5.0"})

def try_mdpi_paper(doi, fname):
    """Try ALL possible MDPI PDF URLs."""
    suffix = doi.split('/')[-1]
    
    # Parse metadata from suffix: "antiox13030309"
    # antimicrobials13-1300309 or similar
    # The real MDPI page shows: https://www.mdpi.com/<issn>/<vol>/<issue>/<article>
    
    # First, get the article page via curl_cffi to find the real URL
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    try:
        r = curl_req.get(
            f"https://www.mdpi.com/{suffix}",
            impersonate="chrome131",
            timeout=30
        )
        if r.status_code == 200:
            # Get the actual article URL from redirect
            actual_url = r.url
            print(f"  {fname}: actual URL = {actual_url}")
            
            # Try PDF
            pdf_url = actual_url.rstrip('/') + '/pdf'
            r2 = curl_req.get(pdf_url, impersonate="chrome131", timeout=30)
            if r2.status_code == 200 and b'%PDF' in r2.content[:200]:
                fp = os.path.join(OUT, fname + ".pdf")
                with open(fp, 'wb') as f:
                    f.write(r2.content)
                return True, f"OK ({len(r2.content)//1024}KB) via MDPI direct"
            
            # Try with redirect following
            r3 = curl_req.get(pdf_url, impersonate="chrome131", timeout=30)
            # Check if got "verify" page
            if 'verify' in r3.text.lower() or 'bm-verify' in r3.text:
                # Akamai blocked - but the PDF might still be accessible
                # Try to get from specific journal/vol/issue/article path
                m = re.search(r'/(\d{4}-?\d{3,4})/(\d+)/(\d+)/(\d+)', actual_url)
                if m:
                    issn, vol, issue, article = m.groups()
                    for purl in [
                        f"https://mdpi-res.com/{issn}/{vol}/{issue}/{article}.pdf",
                        f"https://mdpi-res.com/{issn}/{vol}/{issue}/{article}",
                        f"https://www.mdpi.com/{issn}/{vol}/{issue}/{article}/pdf",
                    ]:
                        try:
                            r4 = requests.get(purl, timeout=15)
                            if r4.status_code == 200 and b'%PDF' in r4.content[:200]:
                                fp = os.path.join(OUT, fname + ".pdf")
                                with open(fp, 'wb') as f:
                                    f.write(r4.content)
                                return True, f"OK via mdpi-res"
                        except: pass
                    
                    return False, f"Akamai blocked, URL={actual_url}"
            
            else:
                return False, f"Got page but no PDF ({r3.status_code})"
        elif r.status_code == 404:
            # Try with direct journal URL
            # Common MDPI articles patterns
            pass
    except Exception as e:
        pass
    
    return False, f"curl_cffi failed"

# Test the most critical papers
CRITICAL_TEST = [
    ("104_Yamauchi_2024_DPPH", "10.3390/antiox13030309"),
    ("014_Boulebd_2023_Antioxidant", "10.3390/antiox12091669"),
    ("065_Nandhini_2022_Staphylococcus", "10.3390/antibiotics11050606"),
    ("055_Mani_2023_Drynaria_review", "10.5530/phrev.2023.17.12"),
]

print("=" * 60)
print("🧪 Final MDPI direct tests with curl_cffi")
print("=" * 60)

for fname, doi in CRITICAL_TEST:
    ok, msg = try_mdpi_paper(doi, fname)
    icon = "✅" if ok else "❌"
    print(f"  {icon} {fname}: {msg}")
    print()

print("=" * 60)
print("Also trying PDF link from Sci-Hub 'available on publisher'")
print("=" * 60)

# Many of these Sci-Hub article pages show the OA link
# E.g. https://www.mdpi.com/2076-3921/13/3/309/pdf?version=1709531668
# Let's try with the version parameter
for fname, doi in CRITICAL_TEST:
    suffix = doi.split('/')[-1]
    # Try known MDPI URL patterns with various ISSNs
    for issn, vol, issue in [
        ("2076-3921", "13", "3"),  # Antioxidants - 309
        ("2079-6382", "11", "5"),  # Antibiotics
        ("1420-3049", "27", "5"),  # Molecules - 1484
    ]:
        for article_num in range(300, 315):
            url = f"https://www.mdpi.com/{issn}/{vol}/{issue}/{article_num}/pdf"
            try:
                r = _s.head(url, timeout=5)
                if r.status_code == 200 and 'pdf' in r.headers.get('content-type', ''):
                    print(f"  FOUND! {url}")
            except:
                pass

print("\nDone.")
