#!/usr/bin/env python3
"""
v6 — Multi-Source Reference PDF Downloader
Extract Daftar Pustaka from DOCX skripsi → find DOIs via CrossRef → download PDFs
from 10+ Open Access sources with automatic fallback.

Usage:
  python v6_multi_source.py "D:\\path\\ke\\skripsi.docx"
  python v6_multi_source.py "D:\\path\\ke\\skripsi.docx" --output "D:/PDFs" --threads 5

Sources (in order):
  1. Semantic Scholar API      — Best hit rate for OA papers
  2. Europe PMC (MED/PMC)      — Many MDPI papers indexed here
  3. CrossRef Full-Text Link   — Publisher direct URLs
  4. Unpaywall API             — Best OA location finder
  5. OpenAlex API              — Comprehensive scholarly graph
  6. Google Cache              — Cached PDFs
  7. CORE API                  — OA aggregator
  8. DOAJ                      — Directory of Open Access Journals
  9. Direct URL guessing       — Known publisher URL patterns
 10. Sci-Hub (fallback)        — Last resort for paywalled papers

Special handling:
  - MDPI papers (10.3390/): Auto-resolved to PubMed Central PMCID→PDF
  - Frontiers papers (10.3389/): Direct OA from Semantic Scholar
  - BMC/Springer OA (10.1186/, most 10.1007/): Direct PDF from link.springer.com
  - Hindawi (10.1155/): Now Wiley, downloads usually blocked
"""
import re, os, json, threading, urllib.parse, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

# ─── CONFIG ───
OUT_DIR = r"D:\Skripsi_Referensi_PDF"
THREADS = 4
TIMEOUT = 30

_print_lock = threading.Lock()
def tprint(*args, **kwargs):
    with _print_lock:
        print(*args, **kwargs)

_s = requests.Session()
_s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
})

# ─── DOI EXTRACTION ───
DOI_RE = re.compile(r'(10\.\d{4,}/[^\s,;)]+)')

def extract_dois_from_docx(docx_path):
    """Extract all DOI references from a DOCX file."""
    from lxml import etree
    try:
        tree = etree.parse(docx_path)
    except Exception as e:
        print(f"❌ Can't parse DOCX: {e}")
        return []
    
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    paragraphs = tree.findall('.//w:p', ns)
    
    in_dapus = False
    dois_found = []
    
    for p in paragraphs:
        text = ''.join(t.text or '' for t in p.findall('.//w:t', ns))
        text_upper = text.strip().upper()
        
        if 'DAFTAR PUSTAKA' in text_upper:
            in_dapus = True
            continue
        if in_dapus and ('LAMPIRAN' in text_upper or 'BIODATA' in text_upper):
            break
        if in_dapus:
            dois = DOI_RE.findall(text)
            for doi in dois:
                doi = doi.rstrip('.,;:') if not doi.endswith('.pdf') else doi
                if doi not in dois_found:
                    dois_found.append(doi)
    
    return dois_found


# ─── SOURCE FUNCTIONS ───

def source_semantic_scholar(doi):
    """Semantic Scholar API → OA PDF link."""
    try:
        r = _s.get(
            f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=openAccessPdf,title",
            timeout=15, headers={"Accept": "application/json"}
        )
        if r.status_code == 200:
            oa = r.json().get("openAccessPdf")
            if oa and oa.get("url"):
                return oa["url"], "Semantic Scholar"
    except: pass
    return None, None


def source_europe_pmc(doi):
    """Europe PMC → find PMCID → download PDF."""
    try:
        r = _s.get(
            f"https://www.ebi.ac.uk/europepmc/api/search?query=DOI:{doi}&format=json&pageSize=1",
            timeout=15
        )
        if r.status_code == 200:
            results = r.json().get("resultList", {}).get("result", [])
            if results and results[0].get("pmcid", "").startswith("PMC"):
                pmcid = results[0]["pmcid"]
                pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/"
                r2 = _s.get(pdf_url, timeout=TIMEOUT, allow_redirects=True)
                if r2.status_code == 200 and b'%PDF' in r2.content[:200]:
                    return r2.content, f"PMC-{pmcid}"
    except: pass
    return None, None


def source_crossref(doi):
    """CrossRef API → direct publisher links."""
    try:
        r = _s.get(f"https://api.crossref.org/works/{doi}", timeout=15)
        if r.status_code == 200:
            for link in r.json().get("message", {}).get("link", []):
                url = link.get("URL", "")
                if url:
                    r2 = _s.get(url, timeout=TIMEOUT, allow_redirects=True)
                    if b'%PDF' in r2.content[:200]:
                        return r2.content, "CrossRef"
    except: pass
    return None, None


def source_unpaywall(doi):
    """Unpaywall API → best OA location."""
    try:
        r = _s.get(f"https://api.unpaywall.org/v2/{doi}?email=thesis@research.local", timeout=15)
        if r.status_code == 200:
            for loc in r.json().get("oa_locations", []):
                url = loc.get("url_for_pdf", "")
                if url:
                    r2 = _s.get(url, timeout=TIMEOUT, allow_redirects=True)
                    if b'%PDF' in r2.content[:200]:
                        return r2.content, "Unpaywall"
    except: pass
    return None, None


def source_openalex(doi):
    """OpenAlex API → comprehensive OA links."""
    try:
        r = _s.get(f"https://api.openalex.org/works/doi:{doi}", timeout=15)
        if r.status_code == 200:
            data = r.json()
            # Check best OA location
            for loc in data.get("locations", []):
                pdf_url = loc.get("pdf_url", "")
                if pdf_url:
                    r2 = _s.get(pdf_url, timeout=TIMEOUT, allow_redirects=True)
                    if b'%PDF' in r2.content[:200]:
                        return r2.content, "OpenAlex"
            # Try primary location
            primary = data.get("primary_location", {})
            if primary.get("pdf_url"):
                r2 = _s.get(primary["pdf_url"], timeout=TIMEOUT, allow_redirects=True)
                if b'%PDF' in r2.content[:200]:
                    return r2.content, "OpenAlex"
    except: pass
    return None, None


def source_google_cache(doi):
    """Google cached PDF version."""
    try:
        r = _s.get(f"https://webcache.googleusercontent.com/search?q=cache:{doi}", timeout=15)
        if b'%PDF' in r.content[:200] and len(r.content) > 10000:
            return r.content, "GoogleCache"
    except: pass
    return None, None


def source_core(doi):
    """CORE API → OA aggregator."""
    try:
        r = _s.get(f"https://api.core.ac.uk/v3/search/outputs?q={doi}&limit=3", timeout=15)
        if r.status_code == 200:
            for res in r.json().get("results", []):
                for loc in res.get("locations", []):
                    url = loc.get("url", "")
                    if url and ('pdf' in url.lower() or 'download' in url.lower()):
                        r2 = _s.get(url, timeout=TIMEOUT, allow_redirects=True)
                        if b'%PDF' in r2.content[:200]:
                            return r2.content, "CORE"
    except: pass
    return None, None


def source_doaj(doi):
    """Directory of Open Access Journals."""
    try:
        r = _s.get(f"https://doaj.org/api/v2/search/articles/{doi}?pageSize=1", timeout=15)
        if r.status_code == 200:
            for res in r.json().get("results", []):
                for link in res.get("bibjson", {}).get("link", []):
                    url = link.get("url", "")
                    if 'pdf' in link.get("content_type", "") or url.endswith('.pdf'):
                        r2 = _s.get(url, timeout=TIMEOUT, allow_redirects=True)
                        if b'%PDF' in r2.content[:200]:
                            return r2.content, "DOAJ"
    except: pass
    return None, None


def source_direct(doi):
    """Direct URL guessing based on publisher patterns."""
    suffix = doi.split('/')[-1]
    urls = []
    
    if '10.3389/' in doi:  # Frontiers
        prefix = doi.split('.')[0].split('/')[1]
        urls = [f"https://www.frontiersin.org/articles/{suffix}/pdf"]
    elif '10.1186/' in doi:  # BMC
        urls = [f"https://link.springer.com/content/pdf/{doi}.pdf"]
    elif '10.1007/' in doi and '10.1007/978' not in doi:
        urls = [f"https://link.springer.com/content/pdf/{doi}.pdf"]
    elif '10.1007/978' in doi:
        urls = [f"https://link.springer.com/content/pdf/{doi}.pdf"]
    elif '10.1016/' in doi:  # Elsevier
        urls = [f"https://doi.org/{doi}"]
    elif '10.1080/' in doi:  # Taylor & Francis
        urls = [f"https://doi.org/{doi}"]
    elif '10.20944/' in doi:  # Preprints
        urls = [f"https://www.preprints.org/manuscript/{suffix}/v1/download"]
    elif '10.1002/' in doi:  # Wiley
        urls = [f"https://onlinelibrary.wiley.com/doi/pdf/{doi}"]
    elif '10.2139/' in doi:  # SSRN
        urls = [f"https://papers.ssrn.com/sol3/papers.cfm?abstract_id={suffix}"]
    elif '10.5772/' in doi:  # IntechOpen
        urls = [f"https://www.intechopen.com/chapters/{suffix}/pdf"]
    elif '10.31219/' in doi:  # OSF
        urls = [f"https://osf.io/{suffix}/download"]
    elif '10.1155/' in doi:
        suf = doi.split('/', 1)[1]
        urls = [f"https://downloads.hindawi.com/journals/ijbm/{suf}.pdf",
                f"https://downloads.hindawi.com/journals/jchem/{suf}.pdf"]
    
    for url in urls:
        try:
            r = _s.get(url, timeout=15, allow_redirects=True)
            if r.status_code == 200 and b'%PDF' in r.content[:200] and len(r.content) > 10000:
                return r.content, "Direct"
        except: pass
    return None, None


def source_scihub(doi):
    """Sci-Hub as last resort."""
    for domain in ['https://sci-hub.se', 'https://sci-hub.ru']:
        try:
            r = _s.get(f"{domain}/{doi}", timeout=30, allow_redirects=True)
            if b'%PDF' in r.content[:200]:
                return r.content, f"SciHub"
            # Check for embedded PDF
            m = re.search(r'embed[^>]+src=["\']([^"\']+\.pdf[^"\']*)["\']', r.text)
            if m:
                pdf_url = m.group(1)
                r2 = _s.get(pdf_url, timeout=TIMEOUT, allow_redirects=True)
                if b'%PDF' in r2.content[:200]:
                    return r2.content, "SciHub"
        except: pass
    return None, None


# ─── PIPELINE ───
SOURCES = [
    ("Semantic Scholar", source_semantic_scholar),
    ("Europe PMC", source_europe_pmc),
    ("CrossRef", source_crossref),
    ("Unpaywall", source_unpaywall),
    ("OpenAlex", source_openalex),
    ("Google Cache", source_google_cache),
    ("CORE", source_core),
    ("DOAJ", source_doaj),
    ("Direct URL", source_direct),
    ("Sci-Hub", source_scihub),
]


def download_paper(doi):
    """Try all sources in order. Returns (content: bytes, source: str) or (None, None)."""
    for name, fn in SOURCES:
        result = fn(doi)
        if result[0] is not None:
            if isinstance(result[0], bytes):
                return result  # Actual PDF data
            elif isinstance(result[0], str):
                # It's a URL — download it
                try:
                    r = _s.get(result[0], timeout=TIMEOUT, allow_redirects=True)
                    if r.status_code == 200 and b'%PDF' in r.content[:200]:
                        return r.content, result[1]
                except: pass
    return None, None


def process_doi(doi, idx, total):
    """Download a single DOI."""
    safe_name = doi.replace('/', '_').replace(':', '_').replace('.', '_')[:60]
    fp = os.path.join(OUT_DIR, f"{safe_name}.pdf")
    
    if os.path.exists(fp) and os.path.getsize(fp) > 5000:
        return "exists", doi, None, None
    
    data, source = download_paper(doi)
    
    if data:
        with open(fp, 'wb') as f:
            f.write(data)
        return "success", doi, len(data)//1024, source
    else:
        return "failed", doi, None, None


# ─── MAIN ───
def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Multi-Source Reference PDF Downloader v6")
    parser.add_argument("docx", nargs="?", help="Path to DOCX file (extract DOIs from Daftar Pustaka)")
    parser.add_argument("--output", "-o", default=OUT_DIR, help="Output directory for PDFs")
    parser.add_argument("--threads", "-t", type=int, default=THREADS, help="Number of parallel threads")
    parser.add_argument("--doi", nargs="*", help="Download specific DOIs directly")
    parser.add_argument("--doi-file", help="File with one DOI per line")
    args = parser.parse_args()
    
    global OUT_DIR, THREADS
    OUT_DIR = args.output
    THREADS = args.threads
    
    print("=" * 60)
    print("📚 Multi-Source Reference PDF Downloader v6")
    print("   Sources: Semantic Scholar, Europe PMC, CrossRef, Unpaywall,")
    print("            OpenAlex, Google Cache, CORE, DOAJ, Direct, Sci-Hub")
    print(f"   Output: {OUT_DIR}")
    print(f"   Threads: {THREADS}")
    print("=" * 60)
    
    dois = []
    
    if args.doi:
        dois = args.doi
    elif args.doi_file:
        with open(args.doi_file) as f:
            dois = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    elif args.docx:
        print(f"\n📄 Extracting DOIs from: {args.docx}")
        dois = extract_dois_from_docx(args.docx)
        print(f"   Found {len(dois)} DOIs")
    
    if not dois:
        print("❌ No DOIs provided. Use --doi, --doi-file, or provide a DOCX path.")
        sys.exit(1)
    
    os.makedirs(OUT_DIR, exist_ok=True)
    
    print(f"\n📥 Downloading {len(dois)} papers with {THREADS} threads...\n")
    
    results = {"success": 0, "failed": [], "exists": 0}
    
    with ThreadPoolExecutor(max_workers=THREADS) as exe:
        futures = {exe.submit(process_doi, doi, i+1, len(dois)): doi for i, doi in enumerate(dois)}
        
        for future in as_completed(futures):
            status, doi, size, source = future.result()
            short_doi = doi[:55] + "..." if len(doi) > 55 else doi
            
            if status == "success":
                tprint(f"  ✅ {short_doi:60s} {size}KB ({source})")
                results["success"] += 1
            elif status == "exists":
                tprint(f"  ⏭️ {short_doi:60s} Already exists")
                results["exists"] += 1
            else:
                tprint(f"  ❌ {short_doi:60s}")
                results["failed"].append(doi)
    
    print(f"\n{'='*60}")
    print(f"📊 RESULT: {results['success']}✅ downloaded | {results['exists']}⏭️ exists | {len(results['failed'])}❌ failed")
    print(f"📁 PDFs saved to: {OUT_DIR}")
    print("=" * 60)
    
    if results["failed"]:
        print(f"\n❌ Failed DOIs ({len(results['failed'])}):")
        for doi in results["failed"][:20]:
            print(f"  • {doi}")
        if len(results["failed"]) > 20:
            print(f"  ... and {len(results['failed'])-20} more")


if __name__ == "__main__":
    main()
