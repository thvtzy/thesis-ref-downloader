#!/usr/bin/env python3
"""
Thesis Reference Downloader v3 🔥
Multi-layer fallback: better Sci-Hub parsing, Unpaywall, direct DOIs, Google Scholar
Parallel, retry, resume, progress bar
"""
import re, os, sys, time, json, zipfile, threading, urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from lxml import etree
import requests

# ─── CONFIG ───
@dataclass
class Config:
    out_dir: str = r"D:\Skripsi_Referensi_PDF"
    docx_path: str = ""
    threads: int = 5
    rate_limit: float = 0.3
    max_retries: int = 3
    timeout: int = 30
    resume: bool = True
    # Priority-ordered Sci-Hub domains (fastest first)
    scihub_domains: list = field(default_factory=lambda: [
        "https://sci-hub.se",
        "https://sci-hub.st",
        "https://sci-hub.ru",
        "https://sci-hub.ee",
        "https://sci-hub.do",
        "https://sci-hub.shop",
    ])

    # New: try direct PDF from these open repositories
    oa_domains: list = field(default_factory=lambda: [
        "https://sci-hub.se",
        "https://sci-hub.st",
    ])

cfg = Config()

# Parse CLI args — skip flags and their values
skip_next = 0
for i, arg in enumerate(sys.argv[1:]):
    if skip_next > 0:
        skip_next -= 1
        continue
    if arg in ("--output", "--threads") and i+2 < len(sys.argv):
        skip_next = 1
        if arg == "--output":
            cfg.out_dir = sys.argv[i+2]
        elif arg == "--threads":
            cfg.threads = int(sys.argv[i+2])
    elif arg.startswith("--output="):
        cfg.out_dir = arg.split("=", 1)[1]
    elif arg.startswith("--threads="):
        cfg.threads = int(arg.split("=", 1)[1])
    elif not arg.startswith("--"):
        cfg.docx_path = arg

if not cfg.docx_path:
    cfg.docx_path = input("Path to skripsi DOCX: ").strip()

# ─── DEFAULTS ───
STOP_WORDS = {'a', 'an', 'the', 'of', 'in', 'on', 'for', 'and', 'to', 'from',
              'with', 'by', 'its', 'is', 'as', 'at', 'or', 'via', 'dan', 'pada',
              'dari', 'untuk', 'dengan', 'suatu', 'sebagai', 'oleh', 'ini',
              'yang', 'di', 'ke', 'their', 'into', 'was', 'are', 'been'}

BUKU_TEKS = {"Cappuccino", "Harborne", "Evans", "Kokate", "Miller"}
JURNAL_LOKAL = {"Damayanti", "Febrina", "Hanin", "Hartoyo", "Mustofa",
                "Nisa", "Novaryatiin", "Rafael", "Rahman", "Ratnasari",
                "Sukma", "Bhakti", "Arnida", "Kuspradini", "Yusasrini",
                "Rudiana", "Rizqi"}

# Thread-safe printer
_print_lock = threading.Lock()
def tprint(*args, **kwargs):
    with _print_lock:
        print(*args, **kwargs)

# Global session with connection pooling
_session = requests.Session()
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
})

# ─── EXTRACT REFS ───
def extract_refs_from_docx(docx_path):
    z = zipfile.ZipFile(docx_path, 'r')
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    with z.open('word/document.xml') as f:
        doc_xml = etree.parse(f)
    paragraphs = doc_xml.findall('.//w:p', ns)
    
    dapus_idx = None
    for i, p in enumerate(paragraphs):
        texts = p.findall('.//w:t', ns)
        full = ''.join(t.text or '' for t in texts).strip()
        if full == 'DAFTAR PUSTAKA' and i > 500:
            dapus_idx = i
            break
    
    if not dapus_idx:
        print("❌ DAFTAR PUSTAKA section not found!")
        return []
    
    entries = []
    for i in range(dapus_idx + 1, len(paragraphs)):
        texts = paragraphs[i].findall('.//w:t', ns)
        full = ''.join(t.text or '' for t in texts).strip()
        if not full:
            continue
        if not re.match(r'^[A-Z\xc9][a-z\xe0-\xff,]+', full) or len(full) <= 25:
            continue
        if re.match(r'^(Lampiran|Gambar|Peserta|Selama|Muhammad|Anggota|Staf|'
                    r'Panitia|Presidium|Mentor|Ketua|Majelis|Asisten|Tim)', full, re.I):
            break
        entries.append(full)
    z.close()
    return entries

# ─── PARSE REF ───
@dataclass
class Ref:
    idx: int
    raw: str
    author: str = ""
    year: str = ""
    short_title: str = ""
    full_title: str = ""
    filename: str = ""
    filepath: str = ""
    status: str = "pending"
    reason: str = ""
    doi: str = ""
    matched_authors: list = field(default_factory=list)

def parse_ref(entry, idx):
    r = Ref(idx=idx, raw=entry)
    r.author = entry.split(',')[0].strip()
    r.author = (r.author.replace('\xe9', 'e').replace('\xed', 'i')
                .replace('\xf3', 'o').replace('\xf1', 'n')
                .replace('\xfc', 'u').replace('\u0111', 'd'))
    r.author = re.sub(r'[^\w\s-]', '', r.author).strip()
    
    year_m = re.search(r'(?<!\d)(?:19|20)\d{2}(?!\d)', entry)
    r.year = year_m.group(0) if year_m else 'nodate'
    
    doi_m = re.search(r'(?:doi|DOI|https?://doi\.org)[:\s]*([^\s,;.]+)', entry)
    if doi_m:
        r.doi = doi_m.group(1).strip()
    
    after_year = entry[year_m.end():].strip() if year_m else entry
    after_year = re.sub(r'^[.\s,;:]+', '', after_year)
    r.full_title = after_year[:100]
    
    words = after_year.split()[:8]
    result = []
    for w in words:
        w = w.strip('.,;:()[]"\'')
        if w.lower() not in STOP_WORDS:
            result.append(w)
        if len(result) >= 5:
            break
    if not result:
        result = [w.strip('.,;:()[]"\'') for w in after_year.split()[:3]]
    short = '_'.join(result)
    short = re.sub(r'[^\w\s-]', '', short)
    short = short.replace(' ', '_')[:60].strip('_')
    r.short_title = short
    
    r.filename = f"{idx:03d}_{r.author}_{r.year}_{short}.pdf"
    r.filepath = os.path.join(cfg.out_dir, r.filename)
    return r

# ─── DOI LOOKUP (IMPROVED) ───
def find_doi_crossref(ref):
    """Search CrossRef for DOI with better author matching."""
    if ref.doi:
        return ref.doi
    
    try:
        # Try with author + title keywords
        title_words = re.sub(r'[^a-z\s]', '', ref.full_title.lower()).split()
        title_words = [w for w in title_words if len(w) > 3 and w not in STOP_WORDS]
        query_terms = [ref.author.split()[-1]] + title_words[:6]
        query = ' '.join(query_terms)
        
        r = _session.get(
            "https://api.crossref.org/works?query=" + urllib.parse.quote(query),
            timeout=cfg.timeout
        )
        data = r.json()
        
        if not data["message"]["items"]:
            return None
        
        # Try exact author match first
        author_last = ref.author.split()[-1].lower()
        for item in data["message"]["items"]:
            doi = item.get("DOI", "")
            authors = item.get("author", [])
            for a in authors:
                family = (a.get("family", "") or "").lower()
                given = (a.get("given", "") or "")
                ref.matched_authors.append(f"{family}, {given}")
                if family == author_last:
                    return doi
        
        # Fall back to first result
        return data["message"]["items"][0]["DOI"]
    except Exception:
        return None

def find_doi_unpaywall(ref, email="anonymous@example.com"):
    """Try Unpaywall API for DOI lookup."""
    try:
        title_encoded = urllib.parse.quote(ref.full_title[:80])
        # Search by title
        r = _session.get(
            f"https://api.unpaywall.org/v2/search?query={title_encoded}&email={email}",
            timeout=cfg.timeout
        )
        if r.status_code == 200:
            data = r.json()
            if data.get("results"):
                for result in data["results"]:
                    doi = result.get("doi", "")
                    if doi:
                        return doi
        return None
    except Exception:
        return None

def find_doi(ref):
    """Multi-source DOI lookup."""
    doi = find_doi_crossref(ref)
    if doi:
        return doi
    doi = find_doi_unpaywall(ref)
    if doi:
        return doi
    return None

# ─── PDF DOWNLOAD STRATEGIES ───

def download_via_scihub_v3(doi):
    """
    v3 Sci-Hub scraper: more robust PDF URL extraction.
    Tries multiple extraction methods from Sci-Hub HTML.
    """
    for domain in cfg.scihub_domains:
        url = f"{domain}/{doi}"
        for attempt in range(cfg.max_retries):
            try:
                resp = _session.get(url, timeout=cfg.timeout)
                if resp.status_code != 200:
                    time.sleep(0.5)
                    continue
                
                html = resp.text
                pdf_url = None
                
                # --- METHOD 1: Direct embed/object tags ---
                patterns = [
                    # <embed src="...pdf">
                    r'<embed[^>]+src\s*=\s*["\']([^"\']+\.pdf[^"\']*)["\']',
                    # <iframe src="...pdf">
                    r'<iframe[^>]+src\s*=\s*["\']([^"\']+\.pdf[^"\']*)["\']',
                    # <object data="...pdf">
                    r'<object[^>]+data\s*=\s*["\']([^"\']+\.pdf[^"\']*)["\']',
                    # Download button with data-pdf or href
                    r'data-pdf\s*=\s*["\']([^"\']+\.pdf[^"\']*)["\']',
                ]
                for pat in patterns:
                    m = re.search(pat, html)
                    if m:
                        pdf_url = m.group(1)
                        break
                
                if not pdf_url:
                    # --- METHOD 2: citation_pdf_url meta tag ---
                    m = re.search(
                        r'citation_pdf_url["\']?\s*(?:content|href)\s*=\s*["\']([^"\']+)["\']',
                        html
                    )
                    if m:
                        pdf_url = m.group(1)
                
                if not pdf_url:
                    # --- METHOD 3: Download button onclick with location.href ---
                    m = re.search(r'onclick\s*=\s*["\']location\.href\s*=\s*["\']([^"\']+)["\']', html)
                    if m:
                        pdf_url = m.group(1)
                
                if not pdf_url:
                    # --- METHOD 4: Look for /downloads/ in any href/script ---
                    m = re.search(
                        r'["\'](https?://[^"\']*/downloads/[^"\']+)["\']', html
                    )
                    if m:
                        pdf_url = m.group(1)
                
                if not pdf_url:
                    # --- METHOD 5: Look for base64 encoded PDF data ---
                    # Some Sci-Hub variants embed base64 PDF
                    m = re.search(r'data:application/pdf;base64,([^"\'<>]+)', html)
                    if m:
                        import base64
                        try:
                            pdf_data = base64.b64decode(m.group(1))
                            if b'%PDF' in pdf_data[:100]:
                                return pdf_data, domain
                        except:
                            pass

                if not pdf_url:
                    # --- METHOD 6: Try fetching direct download URL ---
                    # Sci-Hub sometimes has /downloads/DOINAME.pdf
                    direct_url = f"{domain}/downloads/{doi.replace('/', '-')}.pdf"
                    try:
                        direct_resp = _session.get(direct_url, timeout=cfg.timeout)
                        if direct_resp.status_code == 200 and b'%PDF' in direct_resp.content[:100]:
                            return direct_resp.content, domain
                    except:
                        pass
                    
                    # Also try with just the DOI path
                    direct_url2 = f"{domain}/downloads/{doi.split('/')[-1]}.pdf"
                    try:
                        direct_resp2 = _session.get(direct_url2, timeout=cfg.timeout)
                        if direct_resp2.status_code == 200 and b'%PDF' in direct_resp2.content[:100]:
                            return direct_resp2.content, domain
                    except:
                        pass
                
                if not pdf_url:
                    break  # No PDF found on this domain, try next
                
                # --- RESOLVE PDF URL ---
                if pdf_url.startswith("//"):
                    pdf_url = "https:" + pdf_url
                elif pdf_url.startswith("/"):
                    pdf_url = domain + pdf_url
                elif not pdf_url.startswith("http"):
                    pdf_url = domain + "/" + pdf_url
                
                pdf_url = pdf_url.split('#')[0]
                
                # --- FETCH PDF ---
                time.sleep(0.3)
                pdf_resp = _session.get(pdf_url, timeout=cfg.timeout)
                
                if len(pdf_resp.content) > 5000 and b'%PDF' in pdf_resp.content[:200]:
                    return pdf_resp.content, domain
                
                if attempt < cfg.max_retries - 1:
                    time.sleep(1 * (attempt + 1))
                    
            except Exception:
                if attempt < cfg.max_retries - 1:
                    time.sleep(1 * (attempt + 1))
                continue
    
    return None, None


def download_via_crossref_direct(doi):
    """Try to get PDF directly from CrossRef / publisher."""
    try:
        # Resolve DOI and follow redirects to publisher page
        resp = _session.get(f"https://doi.org/{doi}", timeout=cfg.timeout, allow_redirects=True)
        final_url = resp.url
        
        # Try common PDF URL patterns
        pdf_candidates = [
            final_url.rstrip('/') + '.pdf',
            final_url.rstrip('/') + '/pdf',
            final_url.rstrip('/') + '/download',
            re.sub(r'/abstract|/full|/article|/html$', '/pdf', final_url),
            re.sub(r'/abstract|/full|/article|/html$', '.pdf', final_url),
        ]
        
        # Publisher-specific patterns
        if 'mdpi.com' in final_url:
            doi_suffix = doi.split('/')[-1]
            pdf_candidates.append(f"https://mdpi-res.com/d_attachment/{doi_suffix}/{doi_suffix}.pdf")
        if 'springer' in final_url or 'link.springer' in final_url:
            pdf_candidates.append(final_url + '.pdf')
        if 'tandfonline' in final_url:
            pdf_candidates.append(re.sub(r'/full/', '/pdf/', final_url))
        if 'wiley' in final_url:
            pdf_candidates.append(final_url.replace('/abstract', '/pdf'))
        if 'elsevier' in final_url or 'sciencedirect' in final_url:
            pdf_candidates.append(re.sub(r'/article/', '/article/pii/', final_url) + '/pdf')
        
        for p_url in pdf_candidates:
            try:
                pdf_resp = _session.get(p_url, timeout=cfg.timeout)
                if pdf_resp.status_code == 200 and b'%PDF' in pdf_resp.content[:200]:
                    return pdf_resp.content, p_url[:40]
            except:
                continue
        
        return None, None
    except:
        return None, None


def download_via_unpaywall(doi, email="anonymous@example.com"):
    """Use Unpaywall API to find OA PDF."""
    try:
        r = _session.get(
            f"https://api.unpaywall.org/v2/{doi}?email={email}",
            timeout=cfg.timeout
        )
        if r.status_code == 200:
            data = r.json()
            for location in data.get("oa_locations", []):
                pdf_url = location.get("url_for_pdf") or location.get("pdf_url")
                if pdf_url:
                    pdf_resp = _session.get(pdf_url, timeout=cfg.timeout)
                    if pdf_resp.status_code == 200 and b'%PDF' in pdf_resp.content[:200]:
                        return pdf_resp.content, "unpaywall"
        return None, None
    except:
        return None, None


def download_via_pdf_host(doi):
    """Try common PDF hosts directly."""
    try:
        doi_clean = doi.replace('/', '-')
        doi_suffix = doi.split('/')[-1]
        
        urls = [
            # ResearchGate
            f"https://www.researchgate.net/profile/publication/{doi_suffix}/links/*/{doi_suffix}.pdf",
            # arXiv (if it's an arXiv paper)
            f"https://arxiv.org/pdf/{doi_suffix}.pdf",
            # bioRxiv / medRxiv
            f"https://www.biorxiv.org/content/{doi_suffix}.full.pdf",
            f"https://www.medrxiv.org/content/{doi_suffix}.full.pdf",
            # PubMed Central
            f"https://www.ncbi.nlm.nih.gov/pmc/articles/{doi_suffix}/pdf/",
            # HAL archives
            f"https://hal.science/{doi_suffix}/document",
        ]
        
        for url in urls:
            try:
                resp = _session.get(url, timeout=cfg.timeout)
                if resp.status_code == 200 and b'%PDF' in resp.content[:200]:
                    return resp.content, url.split('/')[2]
            except:
                continue
        return None, None
    except:
        return None, None


def download_pdf(doi):
    """
    Multi-layer PDF download strategy:
    Layer 1: Sci-Hub v3 (improved scraping)
    Layer 2: CrossRef direct links
    Layer 3: Unpaywall OA API
    Layer 4: Direct PDF hosts
    """
    
    # Layer 1: Sci-Hub
    pdf_data, source = download_via_scihub_v3(doi)
    if pdf_data:
        return pdf_data, f"scihub-{source}"
    
    # Layer 2: CrossRef direct
    pdf_data, source = download_via_crossref_direct(doi)
    if pdf_data:
        return pdf_data, "crossref"
    
    # Layer 3: Unpaywall
    pdf_data, source = download_via_unpaywall(doi)
    if pdf_data:
        return pdf_data, "unpaywall"
    
    # Layer 4: Direct PDF hosts
    pdf_data, source = download_via_pdf_host(doi)
    if pdf_data:
        return pdf_data, source
    
    return None, None


# ─── GOOGLE SCHOLAR SEARCH (FINAL FALLBACK) ───
def search_google_scholar(ref):
    """Search Google Scholar for the paper and try to find PDF."""
    try:
        query = f"{ref.author} {ref.year} {ref.short_title.replace('_', ' ')}"
        params = urllib.parse.urlencode({"q": query, "hl": "en"})
        r = _session.get(
            f"https://scholar.google.com/scholar?{params}",
            timeout=cfg.timeout,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        if r.status_code != 200:
            return None, None
        
        # Extract PDF links from Google Scholar
        # Google Scholar links look like: <a href="/url?q=PDF_URL&..."
        pdf_links = re.findall(r'/url\?q=(https?://[^&]+\.pdf)', r.text)
        for link in pdf_links[:3]:
            try:
                pdf_resp = _session.get(
                    urllib.parse.unquote(link),
                    timeout=cfg.timeout,
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                if pdf_resp.status_code == 200 and b'%PDF' in pdf_resp.content[:200]:
                    return pdf_resp.content, "scholar"
            except:
                continue
        
        # Also try to extract regular PDF links
        pdf_links2 = re.findall(r'href=["\'](https?://[^"\']+\.pdf)["\']', r.text)
        for link in pdf_links2[:3]:
            try:
                pdf_resp = _session.get(link, timeout=cfg.timeout)
                if pdf_resp.status_code == 200 and b'%PDF' in pdf_resp.content[:200]:
                    return pdf_resp.content, "scholar"
            except:
                continue
        
        return None, None
    except Exception:
        return None, None


# ─── PROCESS SINGLE REF ───
def process_ref(ref):
    """Process a single reference: lookup DOI + download PDF with multi-layer fallback."""
    # Check if already exists
    if cfg.resume and os.path.exists(ref.filepath) and os.path.getsize(ref.filepath) > 10000:
        ref.status = "exists"
        ref.reason = f"Already exists ({os.path.getsize(ref.filepath)//1024}KB)"
        return ref
    
    # Check known categories
    if ref.author in BUKU_TEKS:
        ref.status = "skipped"
        ref.reason = "Buku teks — Google Books"
        return ref
    
    if ref.author in JURNAL_LOKAL:
        ref.status = "skipped"
        ref.reason = "Jurnal lokal — Google Scholar"
        return ref
    
    # ===== STAGE 1: Find DOI =====
    doi = find_doi(ref)
    if not doi:
        # ===== STAGE 3: Google Scholar fallback =====
        pdf_data, source = search_google_scholar(ref)
        if pdf_data:
            with open(ref.filepath, 'wb') as f:
                f.write(pdf_data)
            ref.status = "success"
            ref.reason = f"OK (Scholar, {len(pdf_data)//1024}KB)"
            return ref
        
        ref.status = "failed"
        ref.reason = "DOI not found even via Unpaywall"
        return ref
    
    ref.doi = doi
    
    # ===== STAGE 2: Download PDF =====
    pdf_data, source = download_pdf(doi)
    if pdf_data is None:
        # ===== STAGE 3: Google Scholar fallback =====
        pdf_data, source = search_google_scholar(ref)
        if pdf_data:
            with open(ref.filepath, 'wb') as f:
                f.write(pdf_data)
            ref.status = "success"
            ref.reason = f"OK (Scholar, {len(pdf_data)//1024}KB)"
            return ref
        
        ref.status = "failed"
        ref.reason = f"All sources failed: DOI={doi}"
        return ref
    
    # Save
    with open(ref.filepath, 'wb') as f:
        f.write(pdf_data)
    
    size_kb = len(pdf_data) // 1024
    ref.status = "success"
    ref.reason = f"OK ({size_kb}KB via {source})"
    return ref


# ─── SUMMARY ───
def print_summary(refs, elapsed):
    success = [r for r in refs if r.status in ("success", "exists")]
    failed = [r for r in refs if r.status == "failed"]
    skipped = [r for r in refs if r.status == "skipped"]
    
    print("\n" + "=" * 70)
    print(f"📊 HASIL ({len(success)} ✅ / {len(failed)} ❌ / {len(skipped)} ⏭️ ) — {elapsed:.1f}s")
    print("=" * 70)
    
    if success:
        print(f"\n✅ BERHASIL ({len(success)}):")
        for r in success:
            print(f"  {r.filename}")
    
    if failed:
        print(f"\n❌ GAGAL ({len(failed)}):")
        for r in failed:
            print(f"  {r.filename}  — {r.reason}")
    
    if skipped:
        print(f"\n⏭️  SKIP ({len(skipped)}):")
        for r in skipped:
            print(f"  {r.filename}  — {r.reason}")
    
    log_path = os.path.join(cfg.out_dir, "download_log.txt")
    failed_path = os.path.join(cfg.out_dir, "failed.txt")
    
    with open(log_path, 'w') as f:
        f.write(f"THESIS REF DOWNLOADER v3 — {time.strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"Source: {cfg.docx_path}\n")
        f.write(f"Total: {len(success)} success, {len(failed)} failed, {len(skipped)} skipped\n\n")
        for r in refs:
            icons = {"success": "✅", "exists": "⏭️", "failed": "❌", "skipped": "⏭️"}
            f.write(f"{icons.get(r.status, '?')} [{r.status.upper()}] {r.filename} - {r.reason}\n")
    
    with open(failed_path, 'w') as f:
        f.write("REFERENSI GAGAL — Coba cari manual di Google Scholar / Google Books\n\n")
        for r in failed + skipped:
            f.write(f"{r.filename}\n  {r.reason}\n  {r.raw[:150]}\n\n")
    
    print(f"\n📄 Log:   {log_path}")
    print(f"📄 Failed: {failed_path}")
    print(f"📁 Folder: {cfg.out_dir}")


# ─── MAIN ───
def main():
    start = time.time()
    
    print("=" * 70)
    print("📚 THESIS REFERENCE DOWNLOADER v3 🔥")
    print(f"   {cfg.docx_path}")
    print(f"   → {cfg.out_dir}")
    print(f"   ⚡ {cfg.threads} threads | Layers: Sci-Hub→CrossRef→Unpaywall→Scholar")
    print("=" * 70)
    
    # Extract references
    print("\n📖 Extracting references...")
    entries = extract_refs_from_docx(cfg.docx_path)
    if not entries:
        print("❌ No references found!")
        return
    
    refs = [parse_ref(e, i) for i, e in enumerate(entries, 1)]
    print(f"✅ {len(refs)} references extracted\n")
    
    os.makedirs(cfg.out_dir, exist_ok=True)
    
    # Filter already existing
    to_download = [r for r in refs if not (cfg.resume and os.path.exists(r.filepath) and os.path.getsize(r.filepath) > 10000)]
    already_have = [r for r in refs if r not in to_download]
    
    for r in already_have:
        r.status = "exists"
        r.reason = f"Already exists ({os.path.getsize(r.filepath)//1024}KB)"
    
    if already_have:
        print(f"⏭️  {len(already_have)} already downloaded — skipped")
    
    # Also re-download previously failed ones
    if to_download:
        print(f"⬇️  Downloading {len(to_download)} files ({cfg.threads} threads, multi-layer)...\n")
        
        with ThreadPoolExecutor(max_workers=cfg.threads) as executor:
            futures = {executor.submit(process_ref, r): r for r in to_download}
            
            done = 0
            for future in as_completed(futures):
                ref = futures[future]
                done += 1
                
                try:
                    result = future.result()
                    icons = {"success": "✅", "exists": "⏭️", "failed": "❌", "skipped": "⏭️", "pending": "⏳"}
                    tprint(f"  [{done:>3}/{len(to_download)}] {icons.get(result.status, '?')} {result.filename}  {result.reason}")
                except Exception as e:
                    tprint(f"  [{done:>3}/{len(to_download)}] ❌ {ref.filename} — Error: {str(e)[:60]}")
                    ref.status = "failed"
                    ref.reason = str(e)[:60]
    
    elapsed = time.time() - start
    print_summary(refs, elapsed)


if __name__ == "__main__":
    main()
