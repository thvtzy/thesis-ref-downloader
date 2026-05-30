#!/usr/bin/env python3
"""
v3.3 — Final push: Unpaywall + CORE API + LibGen + direct methods
Only has the 34 remaining failed DOIs.
"""
import re, os, sys, time, json, threading, urllib.parse, logging
from concurrent.futures import ThreadPoolExecutor, as_completed
logging.disable(logging.CRITICAL)

import requests

OUT_DIR = r"D:\Skripsi_Referensi_PDF"
TIMEOUT = 45
THREADS = 4

_print_lock = threading.Lock()
def tprint(*args, **kwargs):
    with _print_lock:
        print(*args, **kwargs)

_s = requests.Session()
_s.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
})

# ─── 1. UNPAYWALL API ───
def unpaywall_api(doi, email="anonymous@example.org"):
    try:
        r = _s.get(
            f"https://api.unpaywall.org/v2/{doi}?email={email}",
            timeout=TIMEOUT,
            headers={"Accept": "application/json"}
        )
        if r.status_code == 200:
            data = r.json()
            is_oa = data.get("is_oa", False)
            best_loc = data.get("best_oa_location", {}) or {}
            # Try best location first
            pdf_url = best_loc.get("url_for_pdf") or best_loc.get("pdf_url") or ""
            landing = best_loc.get("url_for_landing_page", "")
            
            if pdf_url:
                pdf_r = _s.get(pdf_url, timeout=TIMEOUT)
                if pdf_r.status_code == 200 and b'%PDF' in pdf_r.content[:200]:
                    return pdf_r.content, f"Unpaywall/{best_loc.get('host_type','?')}"
            
            # Try all locations
            for loc in data.get("oa_locations", []):
                pu = loc.get("url_for_pdf") or loc.get("pdf_url") or ""
                if pu:
                    try:
                        pdf_r = _s.get(pu, timeout=TIMEOUT)
                        if pdf_r.status_code == 200 and b'%PDF' in pdf_r.content[:200]:
                            return pdf_r.content, f"Unpaywall/{loc.get('host_type','?')}"
                    except:
                        continue
        return None, None
    except:
        return None, None

# ─── 2. CORE API ───
def core_api(doi, api_key=""):
    """CORE aggregator API (has free tier)"""
    try:
        # Try direct URL first
        url = f"https://core.ac.uk/api-v2/articles/doi/{doi}/download"
        if not api_key:
            # Public endpoint
            r = _s.get(f"https://core.ac.uk/download/{doi.replace('/', '-')}.pdf", timeout=TIMEOUT)
            if r.status_code == 200 and b'%PDF' in r.content[:200]:
                return r.content, "CORE"
        return None, None
    except:
        return None, None

# ─── 3. LIBGEN (Library Genesis) ───
def libgen_search(doi):
    """Search LibGen for a paper."""
    try:
        # Search LibGen via its API-like interface
        r = _s.get(
            f"https://libgen.is/scimag/?q={doi}",
            timeout=TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        if r.status_code == 200:
            # Find download links
            # LibGen's Sci-Mag links look like:
            # <a href="https://libgen.is/scimag10/.../...pdf" 
            # or through libgen.lol etc
            pdf_links = re.findall(r'href=["\'](https?://libgen\.[^"\']+\.pdf)["\']', r.text)
            pdf_links += re.findall(r'href=["\'](https?://[\w.-]+/scimag\d+/[^"\']+\.pdf)["\']', r.text)
            
            for pl in pdf_links:
                try:
                    pr = _s.get(pl, timeout=TIMEOUT)
                    if pr.status_code == 200 and b'%PDF' in pr.content[:200]:
                        return pr.content, "LibGen"
                except:
                    continue
        return None, None
    except:
        return None, None

# ─── 4. GOOGLE SCHOLAR DIRECT ───
def scholar_direct(doi_short):
    """Google Scholar search for paper by DOI suffix."""
    try:
        query = doi_short
        r = _s.get(
            f"https://scholar.google.com/scholar?q=%22{doi_short}%22",
            timeout=TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        if r.status_code == 200:
            # Extract redirect links that might point to PDF
            pdf_refs = re.findall(r'/url\?q=(https?://[^&]+\.pdf)', r.text)
            for ref in pdf_refs[:5]:
                url = urllib.parse.unquote(ref)
                try:
                    pr = _s.get(url, timeout=TIMEOUT)
                    if pr.status_code == 200 and b'%PDF' in pr.content[:200]:
                        return pr.content, "Scholar"
                except:
                    continue
        return None, None
    except:
        return None, None

# ─── 5. SCI-HUB RUS (sometimes different from .st) ───
def scihub_ru(doi):
    """Specifically sci-hub.ru which was working."""
    try:
        r = _s.get(f"https://sci-hub.ru/{doi}", timeout=TIMEOUT)
        html = r.text
        
        # Check if paper available
        if "not available" in html.lower():
            # Maybe has OA link suggestion
            oa_m = re.search(r'href=["\'](https?://[^"\']+\?version=[^"\']+)["\']', html)
            if oa_m:
                pr = _s.get(oa_m.group(1), timeout=TIMEOUT)
                if pr.status_code == 200 and b'%PDF' in pr.content[:200]:
                    return pr.content, "SciHub-OA"
            return None, None
        
        # Extract PDF as before
        patterns = [
            r'<embed[^>]+src\s*=\s*["\']([^"\']+\.pdf[^"\']*)["\']',
            r'<iframe[^>]+src\s*=\s*["\']([^"\']+\.pdf[^"\']*)["\']',
            r'<object[^>]+data\s*=\s*["\']([^"\']+\.pdf[^"\']*)["\']',
            r'citation_pdf_url["\']?\s*content\s*=\s*["\']([^"\']+)["\']',
        ]
        
        for pat in patterns:
            m = re.search(pat, html)
            if m:
                pdf_url = m.group(1)
                if pdf_url.startswith("//"):
                    pdf_url = "https:" + pdf_url
                elif pdf_url.startswith("/"):
                    pdf_url = "https://sci-hub.ru" + pdf_url
                elif not pdf_url.startswith("http"):
                    pdf_url = "https://sci-hub.ru/" + pdf_url
                
                pr = _s.get(pdf_url, timeout=TIMEOUT)
                if pr.status_code == 200 and b'%PDF' in pr.content[:200]:
                    return pr.content, "SciHub.ru"
                
        return None, None
    except:
        return None, None

# ─── 6. DIRECT PUBLISHER PAGES ───
def direct_publisher(doi):
    """Try direct publisher URLs with Accept: application/pdf"""
    try:
        # Try DOI resolution with Accept header for PDF
        h = {
            "Accept": "application/pdf,application/x-pdf,*/*",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        r = _s.get(f"https://doi.org/{doi}", headers=h, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code == 200 and b'%PDF' in r.content[:200]:
            return r.content, "doi.org"
        
        # For specific publishers, try known PDF patterns
        final_url = r.url
        
        # Springer
        if 'springer' in final_url:
            for pattern in ['.pdf', '/pdf', '/download']:
                try:
                    pr = _s.get(final_url.rstrip('/') + pattern, timeout=TIMEOUT)
                    if pr.status_code == 200 and b'%PDF' in pr.content[:200]:
                        return pr.content, "Springer"
                except: pass
        
        # Taylor & Francis
        if 'tandfonline' in final_url:
            pdf_url = re.sub(r'/full/', '/pdf/', final_url)
            try:
                pr = _s.get(pdf_url, timeout=TIMEOUT)
                if pr.status_code == 200 and b'%PDF' in pr.content[:200]:
                    return pr.content, "TandF"
            except: pass
        
        return None, None
    except:
        return None, None

# ─── UNIFIED ───
ALL_DOWNLOADERS = [
    ("Unpaywall", unpaywall_api),
    ("Sci-Hub.ru", scihub_ru),
    ("Publisher", direct_publisher),
    ("LibGen", libgen_search),
    ("CORE", core_api),
    ("Scholar", scholar_direct),
]

def download_everything(doi):
    short = doi.split('/')[-1]
    for name, fn in ALL_DOWNLOADERS:
        try:
            pdf_data, source = fn(doi)
            if pdf_data:
                return pdf_data, name
        except:
            continue
    return None, None


FAILED = [
    ("004_Aisha_2020", "10.46545/aijbls.v2i1.213"),
    ("011_Bakri_2025", "10.35311/jmpi.v11i1.743"),
    ("016_Cao_2025", "10.3390/metabo15120805"),
    ("024_Deepa_2025", "10.69613/h20b8n73"),
    ("026_Divekar_2022", "10.1007/978-3-031-51158-5_24"),
    ("033_Ghorbani_2025", "10.1186/s12870-025-06524-8"),
    ("034_Gulcin_2023", "10.3390/pr11082248"),
    ("039_Huang_2022", "10.3389/fpls.2021.729161"),
    ("048_Kumari_2024", "10.1007/s42535-024-00961-w"),
    ("044_Kandhasamy_2008", "10.13005/bbra/3104"),
    ("050_Lakkana_2024", "10.1080/22311866.2024.2448019"),
    ("053_Liu_2022", "10.3389/fpls.2022.1037582"),
    ("054_Lubos_2011", "10.7828/ajob.v2i1.91"),
    ("055_Mani_2023", "10.5530/phrev.2023.17.12"),
    ("064_Naghavi_2024", "10.2139/ssrn.6712818"),
    ("065_Nandhini_2022", "10.3390/antibiotics11050606"),
    ("070_Okabe_2024", "10.1007/s00795-023-00379-4"),
    ("067_Nikolaou_2023", "10.3390/agronomy13020482"),
    ("072_Platzer_2022", "10.3389/fnut.2022.882458"),
    ("073_Prasanna_2014", "10.5958/0975-4385.2015.00002.3"),
    ("082_Salam_2023", "10.3390/life13030706"),
    ("080_Rodrigues_2023", "10.1016/j.foodchem.2023.137780"),
    ("084_Senawong_2023", "10.1155/2023/4512665"),
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
    ("006_Al-Khayri_2023", "10.3390/metabo13060716"),
    ("014_Boulebd_2023", "10.3390/antiox12091669"),
    ("015_Bouyahya_2022", "10.3390/molecules27051484"),
    ("019_Chang_2024", "10.3390/metabo14080409"),
    ("020_Cronin_2025", "10.26686/wgtn.28308023"),
    ("021_Cruz_2017", "10.20944/preprints201908.0293.v1"),
    ("023_DeRossi_2025", "10.3390/antiox14020200"),
    ("031_Festus_2024", "10.30574/wjarr.2024.22.2.1149"),
    ("040_Jegan_2025", "10.13005/bbra/3367"),
    ("041_Joshi_2020", "10.5530/pj.2021.13.75"),
    ("057_Mehganathan_2022", "10.26420/austinchemeng.2022.1090"),
    ("085_Shaikh_2020", "10.22271/chemi.2020.v8.i2i.8834"),
]

os.makedirs(OUT_DIR, exist_ok=True)

# First check which files actually exist already to skip
existing_files = set()
for f in os.listdir(OUT_DIR):
    if f.endswith('.pdf') and os.path.getsize(os.path.join(OUT_DIR, f)) > 10000:
        existing_files.add(f)

print("=" * 70)
print("📚 v3.3 — Final Push: Unpaywall+CORE+LibGen+Scholar")
print(f"   {len(FAILED)} to attempt | {len(existing_files)} already in folder")
print("=" * 70)

results = {"success": [], "exists": [], "failed": []}

def process(fname, doi):
    filepath = os.path.join(OUT_DIR, fname + ".pdf")
    
    # Check any existing file with same index
    idx = fname.split('_')[0]
    for ef in existing_files:
        if ef.startswith(idx + '_') or ef == fname + '.pdf':
            return "exists", f"Already exists as {ef}"
    if os.path.exists(filepath) and os.path.getsize(filepath) > 10000:
        return "exists", f"Already exists"
    
    pdf_data, source = download_everything(doi)
    if pdf_data:
        with open(filepath, 'wb') as f:
            f.write(pdf_data)
        return "success", f"OK ({len(pdf_data)//1024}KB via {source})"
    else:
        return "failed", f"Gagal total: {doi}"

total = len(FAILED)
with ThreadPoolExecutor(max_workers=THREADS) as exe:
    futures = {exe.submit(process, f, d): (f, d) for f, d in FAILED}
    for i, future in enumerate(as_completed(futures)):
        fname, doi = futures[future]
        try:
            status, reason = future.result()
            results[status].append(fname)
            icons = {"success": "✅", "exists": "⏭️", "failed": "❌"}
            tprint(f"  [{i+1:>2}/{total}] {icons[status]} {fname}  {reason}")
        except Exception as e:
            results["failed"].append(fname)
            tprint(f"  [{i+1:>2}/{total}] ❌ {fname}  Error: {str(e)[:60]}")

print("\n" + "=" * 70)
print(f"📊 FINAL: {len(results['success'])}✅ {len(results['exists'])}⏭️ {len(results['failed'])}❌")
print("=" * 70)
if results['success']:
    print(f"\n✅ BERHASIL baru ({len(results['success'])}):")
    for s in results['success']:
        print(f"  {s}.pdf")
if results['failed']:
    print(f"\n❌ TERSISA ({len(results['failed'])}):")
    for f in results['failed']:
        print(f"  {f}.pdf")
print(f"\n📁 {OUT_DIR}")
