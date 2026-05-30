#!/usr/bin/env python3
"""
v3.2 — Bypass Cloudflare with cloudscraper for MDPI + other OA publishers
Retry only papers that have DOIs but all previous methods failed.
"""
import re, os, sys, time, json, threading, urllib.parse, logging
from concurrent.futures import ThreadPoolExecutor, as_completed
logging.disable(logging.CRITICAL)  # Shut up cloudscraper logs

import cloudscraper
import requests

OUT_DIR = r"D:\Skripsi_Referensi_PDF"
TIMEOUT = 45
THREADS = 4

# Cloudscraper bypasses Cloudflare
_scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'windows',
        'desktop': True,
    },
    delay=3
)

_print_lock = threading.Lock()
def tprint(*args, **kwargs):
    with _print_lock:
        print(*args, **kwargs)

# ─── MDPI DIRECT ───
def download_mdpi_cf(doi):
    """Download MDPI OA paper via Cloudflare-bypassing scraper."""
    try:
        parts = doi.split('/')
        if len(parts) < 2:
            return None, None
        suffix = parts[1]
        
        # MDPI URL patterns (OA — free)
        urls = [
            f"https://www.mdpi.com/{suffix}/pdf",
            f"https://www.mdpi.com/{suffix}/pdf-vor",
            f"https://www.mdpi.com/1420-3049/{suffix}/pdf",
            f"https://www.mdpi.com/2076-3921/{suffix}/pdf",
            f"https://www.mdpi.com/1660-3397/{suffix}/pdf",
            f"https://www.mdpi.com/2072-6643/{suffix}/pdf",
            f"https://www.mdpi.com/2218-273X/{suffix}/pdf",
            f"https://www.mdpi.com/2073-4409/{suffix}/pdf",
        ]
        
        for url in urls:
            try:
                resp = _scraper.get(url, timeout=TIMEOUT)
                if resp.status_code == 200 and b'%PDF' in resp.content[:200]:
                    return resp.content, "MDPI-CF"
                # Check if it redirects to actual article then has PDF link
            except Exception:
                continue
        
        # Try article page first, extract PDF link
        article_url = f"https://www.mdpi.com/{suffix}"
        try:
            resp = _scraper.get(article_url, timeout=TIMEOUT)
            if resp.status_code == 200:
                # Find PDF link in page
                pdf_links = re.findall(r'href=["\']([^"\']+\.pdf[^"\']*)["\']', resp.text)
                for pl in pdf_links:
                    if not pl.startswith('http'):
                        pl = 'https://www.mdpi.com' + pl
                    try:
                        pdf_resp = _scraper.get(pl, timeout=TIMEOUT)
                        if pdf_resp.status_code == 200 and b'%PDF' in pdf_resp.content[:200]:
                            return pdf_resp.content, "MDPI-CF"
                    except:
                        continue
        except:
            pass
        
        return None, None
    except Exception as e:
        return None, None

# ─── FRONTIERS ───
def download_frontiers2(doi):
    try:
        parts = doi.split('/')
        suffix = parts[1] if len(parts) > 1 else parts[0]
        url = f"https://www.frontiersin.org/journals/articles/{suffix}/pdf"
        resp = _scraper.get(url, timeout=TIMEOUT)
        if resp.status_code == 200 and b'%PDF' in resp.content[:200]:
            return resp.content, "Frontiers"
        return None, None
    except:
        return None, None

# ─── PMC ───
def download_pmc2(doi):
    try:
        # Use NCBI API to find PMC ID
        r = _scraper.get(
            f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pmc&term={doi}&retmode=json",
            timeout=TIMEOUT
        )
        if r.status_code == 200:
            data = r.json()
            ids = data.get("esearchresult", {}).get("idlist", [])
            if ids:
                for pmc_id in ids:
                    pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id}/pdf/"
                    resp = _scraper.get(pdf_url, timeout=TIMEOUT)
                    if resp.status_code == 200 and b'%PDF' in resp.content[:200]:
                        return resp.content, "PMC"
        return None, None
    except:
        return None, None

# ─── CORE.AC.UK ───
def download_core2(doi):
    try:
        url = f"https://core.ac.uk/api/direct/doi/{doi}"
        resp = _scraper.get(url, timeout=TIMEOUT)
        if resp.status_code == 200 and b'%PDF' in resp.content[:200]:
            return resp.content, "CORE"
        return None, None
    except:
        return None, None

# ─── DOAJ ───
def download_doaj(doi):
    """Directory of Open Access Journals"""
    try:
        r = _scraper.get(f"https://doaj.org/api/v3/search/articles/{doi}",
                        timeout=TIMEOUT)
        if r.status_code == 200:
            data = r.json()
            results = data.get("results", [])
            for result in results:
                urls = [result.get("bibjson", {}).get("link", [])]
                for link_list in urls:
                    for link in link_list:
                        url = link.get("url", "")
                        if url.endswith(".pdf"):
                            pdf_resp = _scraper.get(url, timeout=TIMEOUT)
                            if pdf_resp.status_code == 200 and b'%PDF' in pdf_resp.content[:200]:
                                return pdf_resp.content, "DOAJ"
        return None, None
    except:
        return None, None

# ─── SCI-HUB WITH CF ───
def download_scihub_cf(doi):
    """Sci-Hub with cloudscraper for better HTML parsing."""
    domains = [
        "https://sci-hub.st",
        "https://sci-hub.ru",
        "https://sci-hub.ee",
        "https://sci-hub.shop",
        "https://sci-hub.se",
    ]
    
    for domain in domains:
        for attempt in range(2):
            try:
                resp = _scraper.get(f"{domain}/{doi}", timeout=TIMEOUT)
                html = resp.text
                
                # Check if paper is available
                if "not available" in html.lower() or "not yet available" in html.lower():
                    # Check if Sci-Hub suggests OA link
                    oa_m = re.search(r'href\s*=\s*["\'](https?://[^"\']+\?version=[^"\']*)["\']', html)
                    if oa_m:
                        oa_url = oa_m.group(1)
                        pdf_resp = _scraper.get(oa_url, timeout=TIMEOUT)
                        if pdf_resp.status_code == 200 and b'%PDF' in pdf_resp.content[:200]:
                            return pdf_resp.content, f"SciHub-OA:{domain[8:]}"
                    # Also try .pdf redirect
                    oa_m2 = re.search(r'href\s*=\s*["\'](https?://[^"\']+\.pdf[^"\']*)["\']', html)
                    if oa_m2:
                        oa_url = oa_m2.group(1)
                        pdf_resp = _scraper.get(oa_url, timeout=TIMEOUT)
                        if pdf_resp.status_code == 200 and b'%PDF' in pdf_resp.content[:200]:
                            return pdf_resp.content, f"SciHub-OA2:{domain[8:]}"
                    continue
                
                # Extract PDF from HTML
                pdf_url = None
                patterns = [
                    r'<embed[^>]+src\s*=\s*["\']([^"\']+\.pdf[^"\']*)["\']',
                    r'<iframe[^>]+src\s*=\s*["\']([^"\']+\.pdf[^"\']*)["\']',
                    r'<object[^>]+data\s*=\s*["\']([^"\']+\.pdf[^"\']*)["\']',
                    r'citation_pdf_url["\']?\s*(?:content|href)\s*=\s*["\']([^"\']+)["\']',
                    r'data-pdf\s*=\s*["\']([^"\']+)["\']',
                    r'onclick\s*=\s*["\']location\.href\s*=\s*["\']([^"\']+)["\']',
                ]
                for pat in patterns:
                    m = re.search(pat, html)
                    if m:
                        pdf_url = m.group(1)
                        break
                
                if not pdf_url:
                    # Direct download URL
                    for dl_pattern in [
                        f"{domain}/downloads/{doi.replace('/', '-')}.pdf",
                        f"{domain}/downloads/{doi.split('/')[-1]}.pdf",
                    ]:
                        try:
                            direct = _scraper.get(dl_pattern, timeout=TIMEOUT)
                            if direct.status_code == 200 and b'%PDF' in direct.content[:200]:
                                return direct.content, f"SHDirect:{domain[8:]}"
                        except:
                            pass
                    continue
                
                # Resolve URL
                if pdf_url.startswith("//"):
                    pdf_url = "https:" + pdf_url
                elif pdf_url.startswith("/"):
                    pdf_url = domain + pdf_url
                elif not pdf_url.startswith("http"):
                    pdf_url = domain + "/" + pdf_url
                
                pdf_resp = _scraper.get(pdf_url, timeout=TIMEOUT)
                if pdf_resp.status_code == 200 and b'%PDF' in pdf_resp.content[:200]:
                    return pdf_resp.content, f"SciHub:{domain[8:]}"
                    
            except Exception:
                continue
    
    return None, None


# ─── UNIFIED DOWNLOADER ───
DOWNLOADERS = [
    ("MDPI-CF", lambda d: download_mdpi_cf(d)),
    ("Sci-Hub CF", lambda d: download_scihub_cf(d)),
    ("Frontiers", lambda d: download_frontiers2(d)),
    ("PMC", lambda d: download_pmc2(d)),
    ("CORE", lambda d: download_core2(d)),
    ("DOAJ", lambda d: download_doaj(d)),
]

def try_all(doi):
    for name, fn in DOWNLOADERS:
        try:
            pdf_data, source = fn(doi)
            if pdf_data:
                return pdf_data, f"{name}/{source}"
        except Exception:
            continue
    return None, None


# ─── DATA ───
FAILED_DOIS = [
    ("004_Aisha_2020", "10.46545/aijbls.v2i1.213"),
    ("006_Al-Khayri_2023", "10.3390/metabo13060716"),
    ("009_Bai_2025", "10.1002/cbdv.202402034"),
    ("011_Bakri_2025", "10.35311/jmpi.v11i1.743"),
    ("012_Baliyan_2022", "10.3390/molecules27041326"),
    ("014_Boulebd_2023", "10.3390/antiox12091669"),
    ("015_Bouyahya_2022", "10.3390/molecules27051484"),
    ("016_Cao_2025", "10.3390/metabo15120805"),
    ("019_Chang_2024", "10.3390/metabo14080409"),
    ("020_Cronin_2025", "10.26686/wgtn.28308023"),
    ("021_Cruz_2017", "10.20944/preprints201908.0293.v1"),
    ("023_DeRossi_2025", "10.3390/antiox14020200"),
    ("024_Deepa_2025", "10.69613/h20b8n73"),
    ("026_Divekar_2022", "10.1007/978-3-031-51158-5_24"),
    ("031_Festus_2024", "10.30574/wjarr.2024.22.2.1149"),
    ("033_Ghorbani_2025", "10.1186/s12870-025-06524-8"),
    ("034_Gulcin_2023", "10.3390/pr11082248"),
    ("039_Huang_2022", "10.3389/fpls.2021.729161"),
    ("040_Jegan_2025", "10.13005/bbra/3367"),
    ("041_Joshi_2020", "10.5530/pj.2021.13.75"),
    ("044_Kandhasamy_2008", "10.13005/bbra/3104"),
    ("048_Kumari_2024", "10.1007/s42535-024-00961-w"),
    ("050_Lakkana_2024", "10.1080/22311866.2024.2448019"),
    ("053_Liu_2022", "10.3389/fpls.2022.1037582"),
    ("054_Lubos_2011", "10.7828/ajob.v2i1.91"),
    ("055_Mani_2023", "10.5530/phrev.2023.17.12"),
    ("057_Mehganathan_2022", "10.26420/austinchemeng.2022.1090"),
    ("064_Naghavi_2024", "10.2139/ssrn.6712818"),
    ("065_Nandhini_2022", "10.3390/antibiotics11050606"),
    ("067_Nikolaou_2023", "10.3390/agronomy13020482"),
    ("070_Okabe_2024", "10.1007/s00795-023-00379-4"),
    ("072_Platzer_2022", "10.3389/fnut.2022.882458"),
    ("073_Prasanna_2014", "10.5958/0975-4385.2015.00002.3"),
    ("080_Rodrigues_2023", "10.1016/j.foodchem.2023.137780"),
    ("082_Salam_2023", "10.3390/life13030706"),
    ("084_Senawong_2023", "10.1155/2023/4512665"),
    ("085_Shaikh_2020", "10.22271/chemi.2020.v8.i2i.8834"),
    ("086_Shamsudin_2022", "10.3390/molecules27041149"),
    ("091_Sultana_2024", "10.3390/molecules29215161"),
    ("092_Sun_2023", "10.5772/intechopen.99799"),
    ("095_Thulasi_2023", "10.4103/jdras.jdras_168_22"),
    ("096_Todorov_2023", "10.3390/ph16050651"),
    ("097_Viji_2013", "10.1201/9781003100768-5"),
    ("098_Vojvodic_2023", "10.1016/j.jfca.2023.105483"),
    ("099_Wang_2024", "10.3724/j.issn.1000-0518.2010.01.117121"),
    ("100_Wang_2025", "10.1186/s12879-025-10484-7"),
    ("103_Woumbo_2021", "10.1155/2021/4869909"),
    ("104_Yamauchi_2024", "10.3390/antiox13030309"),
]


os.makedirs(OUT_DIR, exist_ok=True)

print("=" * 70)
print("📚 THESIS REF DOWNLOADER v3.2 🔥")
print("   Cloudflare bypass (cloudscraper) for MDPI + OA publishers")
print(f"   {len(FAILED_DOIS)} papers to retry | {THREADS} threads")
print("=" * 70)

def process(fname, doi):
    filepath = os.path.join(OUT_DIR, fname + ".pdf")
    
    if os.path.exists(filepath) and os.path.getsize(filepath) > 10000:
        return "exists", f"Already exists ({os.path.getsize(filepath)//1024}KB)"
    
    # Find matching file on disk (maybe different name)
    for existing in os.listdir(OUT_DIR):
        if existing.endswith(".pdf") and fname.split('_')[0] in existing:
            if os.path.getsize(os.path.join(OUT_DIR, existing)) > 10000:
                return "exists", f"Exists as {existing}"
    
    pdf_data, source = try_all(doi)
    if pdf_data:
        with open(filepath, 'wb') as f:
            f.write(pdf_data)
        return "success", f"OK ({len(pdf_data)//1024}KB via {source})"
    else:
        return "failed", f"All methods failed: {doi}"

with ThreadPoolExecutor(max_workers=THREADS) as exe:
    futures = {exe.submit(process, fname, doi): (fname, doi) for fname, doi in FAILED_DOIS}
    total = len(FAILED_DOIS)
    success, failed, exists = [], [], []
    
    for future in as_completed(futures):
        fname, doi = futures[future]
        try:
            status, reason = future.result()
            icons = {"success": "✅", "exists": "⏭️", "failed": "❌"}
            done = len(success) + len(failed) + len(exists)
            tprint(f"  [{done+1:>2}/{total}] {icons.get(status, '?')} {fname}  {reason}")
            if status == "success":
                success.append(fname)
            elif status == "exists":
                exists.append(fname)
            else:
                failed.append(fname)
        except Exception as e:
            done = len(success) + len(failed) + len(exists)
            tprint(f"  [{done+1:>2}/{total}] ❌ {fname}  Error: {str(e)[:60]}")
            failed.append(fname)

print("\n" + "=" * 70)
print(f"📊 HASIL: +{len(success)}✅ baru / {len(exists)}⏭️ udah / {len(failed)}❌ masih gagal")
print("=" * 70)
if success:
    print(f"\n✅ BARU ({len(success)}):")
    for s in success:
        print(f"  {s}.pdf")
if failed:
    print(f"\n❌ TERSISA ({len(failed)}):")
    for f in failed:
        print(f"  {f}.pdf")
print(f"\n📁 Folder: {OUT_DIR}")
