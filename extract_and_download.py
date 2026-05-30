#!/usr/bin/env python3
"""
Thesis Reference Downloader
Extract references from DOCX → Find DOI → Download from Sci-Hub

Usage:
    python extract_and_download.py "path/to/skripsi.docx"
    
Output: D:\Skripsi_Referensi_PDF\ (or custom path)
"""
import re, os, sys, time, json, zipfile
from lxml import etree
import requests

# ─── CONFIG ───
OUT_DIR = r"D:\Skripsi_Referensi_PDF"
RATE_LIMIT = 1.5  # seconds between requests

# ─── HELPERS ───
session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})

STOP_WORDS = {'a', 'an', 'the', 'of', 'in', 'on', 'for', 'and', 'to', 'from',
              'with', 'by', 'its', 'is', 'as', 'at', 'or', 'via', 'dan', 'pada',
              'dari', 'untuk', 'dengan', 'suatu', 'sebagai', 'oleh', 'ini',
              'yang', 'di', 'ke', 'their', 'into', 'was', 'are', 'been'}

BUKU_TEKS = [
    "Cappuccino", "Harborne", "Evans", "Kokate", "Miller"
]

JURNAL_LOKAL = [
    "Damayanti", "Febrina", "Hanin", "Hartoyo", "Mustofa",
    "Nisa", "Novaryatiin", "Rafael", "Rahman", "Ratnasari",
    "Sukma", "Bhakti"
]


def extract_refs_from_docx(docx_path):
    """Extract reference entries from Daftar Pustaka section."""
    z = zipfile.ZipFile(docx_path, 'r')
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    
    with z.open('word/document.xml') as f:
        doc_xml = etree.parse(f)
    
    paragraphs = doc_xml.findall('.//w:p', ns)
    
    # Find DAFTAR PUSTAKA header
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


def parse_ref(entry):
    """Extract author, year, and title from a reference entry."""
    # First author (before first comma)
    first_author = entry.split(',')[0].strip()
    first_author = (first_author.replace('\xe9', 'e').replace('\xed', 'i')
                    .replace('\xf3', 'o').replace('\xf1', 'n')
                    .replace('\xfc', 'u').replace('\u0111', 'd'))
    first_author = re.sub(r'[^\w\s-]', '', first_author).strip()
    
    # Year
    year_m = re.search(r'(?<!\d)(?:19|20)\d{2}(?!\d)', entry)
    year = year_m.group(0) if year_m else 'nodate'
    
    # Title (everything after the year)
    after_year = entry[year_m.end():].strip() if year_m else entry
    after_year = re.sub(r'^[.\s,;:]+', '', after_year)
    
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
    short_title = '_'.join(result)
    short_title = re.sub(r'[^\w\s-]', '', short_title)
    short_title = short_title.replace(' ', '_')[:60].strip('_')
    
    return first_author, year, short_title, after_year[:100]


def make_filename(first_author, year, short_title, idx):
    """Generate PDF filename."""
    return f"{idx:03d}_{first_author}_{year}_{short_title}.pdf"


def find_doi(author, year, title):
    """Search CrossRef for DOI."""
    try:
        q = f"{author} {year} {title[:60]}"
        r = session.get("https://api.crossref.org/works?query=" 
                        + requests.utils.quote(q), timeout=15)
        data = r.json()
        
        if not data["message"]["items"]:
            return None
        
        doi = data["message"]["items"][0]["DOI"]
        # Verify author match
        authors_str = json.dumps(data["message"]["items"][0].get("author", [])).lower()
        if author.lower() not in authors_str:
            return None, f"Author mismatch: {doi}"
        
        return doi, None
    except Exception as e:
        return None, str(e)[:60]


def download_from_scihub(doi):
    """Download PDF from Sci-Hub using DOI."""
    time.sleep(RATE_LIMIT)
    
    sci_url = f"https://sci-hub.ru/{doi}"
    resp = session.get(sci_url, timeout=30)
    html = resp.text
    
    # Try different patterns to find PDF URL
    patterns = [
        r'<object[^>]*data\s*=\s*["\']([^"\']+\.pdf[^"\']*)["\']',
        r'<div class\s*=\s*"download"[^>]*><a[^>]*href\s*=\s*["\']([^"\']+\.pdf[^"\']*)["\']',
        r'fetch\(["\']([^"\']+\.pdf[^"\']*)["\']',
    ]
    
    pdf_path = None
    for pat in patterns:
        m = re.search(pat, html)
        if m:
            pdf_path = m.group(1)
            break
    
    if not pdf_path:
        return None
    
    # Resolve full URL
    if pdf_path.startswith("//"):
        pdf_url = "https:" + pdf_path
    elif pdf_path.startswith("/"):
        pdf_url = "https://sci-hub.ru" + pdf_path
    elif pdf_path.startswith("http"):
        pdf_url = pdf_path
    else:
        pdf_url = "https://sci-hub.ru/" + pdf_path
    
    # Clean fragment
    pdf_url = pdf_url.split('#')[0]
    
    time.sleep(1)
    pdf_resp = session.get(pdf_url, timeout=30)
    
    if len(pdf_resp.content) > 10000 and b'%PDF' in pdf_resp.content[:100]:
        return pdf_resp.content
    
    return None


def download_ref(first_author, year, short_title, full_title, idx, out_dir):
    """Try to download a single reference. Returns (success, reason)."""
    filename = make_filename(first_author, year, short_title, idx)
    filepath = os.path.join(out_dir, filename)
    
    # Skip if exists
    if os.path.exists(filepath) and os.path.getsize(filepath) > 10000:
        return True, "Already exists"
    
    # Skip known books
    if first_author in BUKU_TEKS:
        return False, "BUKU — Google Books / Perpus"
    
    # Skip known local journals
    if first_author in JURNAL_LOKAL:
        return False, "JURNAL LOKAL — Google Scholar"
    
    # Find DOI
    doi, err = find_doi(first_author, year, full_title)
    if not doi:
        return False, f"DOI not found: {err or 'no results'}"
    
    # Download from Sci-Hub
    pdf_data = download_from_scihub(doi)
    if pdf_data is None:
        return False, f"Sci-Hub no PDF: {doi}"
    
    # Save
    with open(filepath, 'wb') as f:
        f.write(pdf_data)
    
    size_kb = len(pdf_data) // 1024
    return True, f"OK ({size_kb}KB)"


def main():
    # Parse args
    if len(sys.argv) > 1:
        docx_path = sys.argv[1]
    else:
        docx_path = input("Path to skripsi DOCX: ").strip()
    
    if not os.path.exists(docx_path):
        print(f"❌ File not found: {docx_path}")
        return
    
    # Create output dir
    out_dir = OUT_DIR
    if len(sys.argv) > 2:
        out_dir = sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    
    print("=" * 70)
    print(f"Thesis Reference Downloader")
    print(f"DOCX: {docx_path}")
    print(f"OUT:  {out_dir}")
    print("=" * 70)
    
    # Extract references
    print("\n📖 Extracting references...")
    entries = extract_refs_from_docx(docx_path)
    
    if not entries:
        print("❌ No references found!")
        return
    
    print(f"✅ Found {len(entries)} references\n")
    
    # Process each entry
    results = []
    for i, entry in enumerate(entries, 1):
        author, year, short_title, full_title = parse_ref(entry)
        filename = make_filename(author, year, short_title, i)
        
        print(f"  [{i:>3}/{len(entries)}] {author} {year}...", end=" ", flush=True)
        success, reason = download_ref(author, year, short_title, full_title, i, out_dir)
        
        status = "✅" if success else "❌"
        print(f"{status} {reason}")
        results.append((i, filename, "SUCCESS" if success else "FAILED", reason))
    
    # Summary
    success_count = sum(1 for r in results if r[2] == "SUCCESS")
    fail_count = sum(1 for r in results if r[2] == "FAILED")
    
    print("\n" + "=" * 70)
    print(f"📊 RESULTS: {success_count} ✅ success / {fail_count} ❌ failed")
    print("=" * 70)
    
    # Save logs
    log_path = os.path.join(out_dir, "download_log.txt")
    with open(log_path, 'w') as f:
        f.write(f"DOWNLOAD LOG - {success_count} success, {fail_count} failed\n\n")
        for i, fn, status, notes in results:
            f.write(f"[{status}] {fn} - {notes}\n")
    
    failed_path = os.path.join(out_dir, "failed.txt")
    with open(failed_path, 'w') as f:
        f.write("REFERENSI YANG GAGAL DIDOWNLOAD:\n")
        f.write("Cari manual di Google Scholar / Google Books\n\n")
        for i, fn, status, notes in results:
            if status == "FAILED":
                f.write(f"{fn} - {notes}\n")
    
    print(f"\n📄 Log:   {log_path}")
    print(f"📄 Failed: {failed_path}")
    print(f"📁 Folder: {out_dir}")


if __name__ == "__main__":
    main()
