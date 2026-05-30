#!/usr/bin/env python3
"""
Thesis Reference Downloader v2 🚀
Parallel download, multi-domain Sci-Hub, retry, resume, progress bar

Usage:
    python extract_and_download.py "path/to/skripsi.docx"
    python extract_and_download.py "path/to/skripsi.docx" --output "D:/PDFs" --threads 5
"""
import re, os, sys, time, json, zipfile, threading
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
    rate_limit: float = 0.3  # per request (with parallel, total QPS = threads/rate_limit)
    max_retries: int = 3
    timeout: int = 25
    resume: bool = True  # skip already downloaded
    scihub_domains: list = field(default_factory=lambda: [
        "https://sci-hub.ru",
        "https://sci-hub.se",
        "https://sci-hub.st",
        "https://sci-hub.ee",
    ])

cfg = Config()

# Parse CLI args
for i, arg in enumerate(sys.argv[1:]):
    if arg == "--output" and i+2 < len(sys.argv):
        cfg.out_dir = sys.argv[i+2]
    elif arg == "--threads" and i+2 < len(sys.argv):
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
                "Sukma", "Bhakti"}

# Thread-safe printer
_print_lock = threading.Lock()
def tprint(*args, **kwargs):
    with _print_lock:
        print(*args, **kwargs)

# ─── EXTRACT REFS ───
def extract_refs_from_docx(docx_path):
    """Extract reference entries from Daftar Pustaka section."""
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

def parse_ref(entry, idx):
    """Parse a reference entry into structured data."""
    r = Ref(idx=idx, raw=entry)
    
    # First author
    r.author = entry.split(',')[0].strip()
    r.author = (r.author.replace('\xe9', 'e').replace('\xed', 'i')
                .replace('\xf3', 'o').replace('\xf1', 'n')
                .replace('\xfc', 'u').replace('\u0111', 'd'))
    r.author = re.sub(r'[^\w\s-]', '', r.author).strip()
    
    # Year
    year_m = re.search(r'(?<!\d)(?:19|20)\d{2}(?!\d)', entry)
    r.year = year_m.group(0) if year_m else 'nodate'
    
    # DOI in entry?
    doi_m = re.search(r'(?:doi|DOI|https?://doi\.org)[:\s]*([^\s,;.]+)', entry)
    if doi_m:
        r.doi = doi_m.group(1).strip()
    
    # Title after year
    after_year = entry[year_m.end():].strip() if year_m else entry
    after_year = re.sub(r'^[.\s,;:]+', '', after_year)
    r.full_title = after_year[:100]
    
    # Short title for filename
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

# ─── DOI LOOKUP ───
def find_doi(ref):
    """Search CrossRef for DOI."""
    if ref.doi:
        return ref.doi  # Already has DOI embedded
    
    try:
        q = f"{ref.author} {ref.year} {ref.full_title[:60]}"
        r = requests.get("https://api.crossref.org/works?query=" 
                        + requests.utils.quote(q),
                        headers={"User-Agent": "Mozilla/5.0"},
                        timeout=cfg.timeout)
        data = r.json()
        
        if not data["message"]["items"]:
            return None
        
        doi = data["message"]["items"][0]["DOI"]
        return doi
    except:
        return None

# ─── DOWNLOAD FROM SCI-HUB ───
def download_from_scihub(doi):
    """Try multiple Sci-Hub domains to download PDF."""
    for domain in cfg.scihub_domains:
        for attempt in range(cfg.max_retries):
            try:
                sci_url = f"{domain}/{doi}"
                resp = requests.get(sci_url,
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=cfg.timeout)
                
                if resp.status_code != 200:
                    time.sleep(0.5)
                    continue
                
                html = resp.text
                
                # Try different patterns
                patterns = [
                    r'<object[^>]*data\s*=\s*["\']([^"\']+\.pdf[^"\']*)["\']',
                    r'<div class\s*=\s*"download"[^>]*><a[^>]*href\s*=\s*["\']([^"\']+\.pdf[^"\']*)["\']',
                    r'fetch\(["\']([^"\']+\.pdf[^"\']*)["\']',
                    r'<iframe[^>]*src\s*=\s*["\']([^"\']+\.pdf[^"\']*)["\']',
                ]
                
                pdf_path = None
                for pat in patterns:
                    m = re.search(pat, html)
                    if m:
                        pdf_path = m.group(1)
                        break
                
                if not pdf_path:
                    # Check meta tag
                    m = re.search(r'citation_pdf_url["\']\s*content\s*=\s*["\']([^"\']+)["\']', html)
                    if m:
                        pdf_path = m.group(1)
                
                if pdf_path:
                    if pdf_path.startswith("//"):
                        pdf_url = "https:" + pdf_path
                    elif pdf_path.startswith("/"):
                        pdf_url = domain + pdf_path
                    elif pdf_path.startswith("http"):
                        pdf_url = pdf_path
                    else:
                        pdf_url = domain + "/" + pdf_path
                    
                    pdf_url = pdf_url.split('#')[0]
                    
                    time.sleep(0.3)
                    pdf_resp = requests.get(pdf_url,
                        headers={"User-Agent": "Mozilla/5.0"},
                        timeout=cfg.timeout)
                    
                    if len(pdf_resp.content) > 10000 and b'%PDF' in pdf_resp.content[:100]:
                        return pdf_resp.content, domain
                
            except Exception:
                if attempt < cfg.max_retries - 1:
                    time.sleep(1 * (attempt + 1))
                continue
    
    return None, None

# ─── PROCESS SINGLE REF ───
def process_ref(ref):
    """Process a single reference: lookup DOI + download PDF."""
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
    
    # Find DOI
    doi = find_doi(ref)
    if not doi:
        ref.status = "failed"
        ref.reason = "DOI not found"
        return ref
    
    ref.doi = doi
    
    # Download
    pdf_data, domain = download_from_scihub(doi)
    if pdf_data is None:
        ref.status = "failed"
        ref.reason = f"Sci-Hub: {doi}"
        return ref
    
    # Save
    with open(ref.filepath, 'wb') as f:
        f.write(pdf_data)
    
    size_kb = len(pdf_data) // 1024
    ref.status = "success"
    ref.reason = f"OK ({size_kb}KB)"
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
    
    # Save logs
    log_path = os.path.join(cfg.out_dir, "download_log.txt")
    failed_path = os.path.join(cfg.out_dir, "failed.txt")
    
    with open(log_path, 'w') as f:
        f.write(f"THESIS REF DOWNLOADER v2 — {time.strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"Source: {cfg.docx_path}\n")
        f.write(f"Total: {len(success)} success, {len(failed)} failed, {len(skipped)} skipped\n\n")
        for r in refs:
            icons = {"success": "✅", "exists": "⏭️", "failed": "❌", "skipped": "⏭️"}
            f.write(f"{icons.get(r.status, '?')} [{r.status.upper()}] {r.filename} - {r.reason}\n")
    
    with open(failed_path, 'w') as f:
        f.write("REFERENSI GAGAL — Cari manual di Google Scholar / Google Books\n\n")
        for r in failed + skipped:
            f.write(f"{r.filename}\n  {r.reason}\n  {r.raw[:120]}\n\n")
    
    print(f"\n📄 Log:   {log_path}")
    print(f"📄 Failed: {failed_path}")
    print(f"📁 Folder: {cfg.out_dir}")

# ─── MAIN ───
def main():
    start = time.time()
    
    print("=" * 70)
    print("📚 THESIS REFERENCE DOWNLOADER v2")
    print(f"   {cfg.docx_path}")
    print(f"   → {cfg.out_dir}")
    print(f"   ⚡ {cfg.threads} threads | {'Resume ON' if cfg.resume else 'Resume OFF'}")
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
    
    # Download in parallel
    if to_download:
        print(f"⬇️  Downloading {len(to_download)} files ({cfg.threads} threads)...\n")
        
        with ThreadPoolExecutor(max_workers=cfg.threads) as executor:
            futures = {executor.submit(process_ref, r): r for r in to_download}
            
            done = 0
            for future in as_completed(futures):
                ref = futures[future]
                done += 1
                
                try:
                    result = future.result()
                    icons = {"success": "✅", "exists": "⏭️", "failed": "❌", "skipped": "⏭️", "pending": "⏳"}
                    tprint(f"  [{done:>3}/{len(to_download)}] {icons.get(result.status, '?')} {result.filename}")
                except Exception as e:
                    tprint(f"  [{done:>3}/{len(to_download)}] ❌ {ref.filename} — Error: {str(e)[:50]}")
                    ref.status = "failed"
                    ref.reason = str(e)[:60]
    
    elapsed = time.time() - start
    print_summary(refs, elapsed)


if __name__ == "__main__":
    main()
