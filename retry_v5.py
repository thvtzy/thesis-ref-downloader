#!/usr/bin/env python3
"""v5 — curl_cffi browser impersonation for MDPI + all OA sources"""
from curl_cffi import requests as curl_req
import re, os, json, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests as std_req

OUT = r"D:\Skripsi_Referensi_PDF"
TIMEOUT = 30
THREADS = 2

_print_lock = threading.Lock()
def tprint(*args, **kwargs):
    with _print_lock:
        print(*args, **kwargs)

# Standard session for non-CDN
_s = std_req.Session()
_s.headers.update({"User-Agent": "Mozilla/5.0"})

def download_mdpi_curl(doi):
    """Use curl_cffi with browser TLS fingerprint for MDPI."""
    suffix = doi.split('/')[-1]
    
    for attempt in range(3):
        try:
            # Step 1: Get the article page (this redirects to correct URL)
            r = curl_req.get(
                f"https://www.mdpi.com/{suffix}",
                impersonate="chrome131",
                timeout=TIMEOUT
            )
            
            if r.status_code == 200:
                actual_url = r.url
                html = r.text
                
                # Step 2: Find PDF link in HTML
                pdf_url = None
                
                # Look for citation_pdf_url
                m = re.search(r'citation_pdf_url["\']?\s*content\s*=\s*["\']([^"\']+)["\']', html)
                if m: pdf_url = m.group(1)
                
                # Look for download PDF link
                if not pdf_url:
                    m = re.search(r'href=["\']([^"\']+/pdf(?:[?][^"\']*)?)["\']', html)
                    if m: pdf_url = m.group(1)
                
                # Look in script data
                if not pdf_url:
                    m = re.search(r'"pdfUrl"\s*:\s*"([^"]+)"', html)
                    if m: pdf_url = m.group(1)
                
                if pdf_url:
                    if pdf_url.startswith('/'):
                        pdf_url = 'https://www.mdpi.com' + pdf_url
                    elif not pdf_url.startswith('http'):
                        pdf_url = 'https://www.mdpi.com/' + pdf_url
                    
                    r2 = curl_req.get(pdf_url, impersonate="chrome131", timeout=TIMEOUT)
                    if r2.status_code == 200 and b'%PDF' in r2.content[:200]:
                        return r2.content, "MDPI-CURL"
                
                # Step 3: Try known URL structure from actual_url
                # e.g. https://www.mdpi.com/2076-3921/13/3/309
                m = re.search(r'/(\d{4}-?\d{3,4})/(\d+)/(\d+)/(\d+)$', actual_url)
                if not m:
                    m = re.search(r'/(\d{4,7})/(\d+)/(\d+)/(\d+)$', actual_url)
                if m:
                    issn, vol, issue, article = m.groups()
                    for purl in [
                        f"https://www.mdpi.com/{issn}/{vol}/{issue}/{article}/pdf",
                        f"https://www.mdpi.com/{issn}/{vol}/{issue}/{article}/pdf-vor",
                        f"https://mdpi-res.com/{issn}/{vol}/{issue}/{article}.pdf",
                    ]:
                        try:
                            r3 = curl_req.get(purl, impersonate="chrome131", timeout=TIMEOUT)
                            if r3.status_code == 200 and b'%PDF' in r3.content[:200]:
                                return r3.content, "MDPI-CURL2"
                        except: pass
                
                # Step 4: Try the direct suffix PDF with curl
                r4 = curl_req.get(
                    f"https://www.mdpi.com/{suffix}/pdf",
                    impersonate="chrome131",
                    timeout=TIMEOUT
                )
                if r4.status_code == 200 and b'%PDF' in r4.content[:200]:
                    return r4.content, "MDPI-Suffix"
                    
        except Exception as e:
            if attempt == 2:
                return None, None
            continue
    
    return None, None

def download_other(doi):
    """Non-MDPI papers via standard methods."""
    # Semantic Scholar
    try:
        r = _s.get(
            f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=openAccessPdf",
            timeout=TIMEOUT
        )
        if r.status_code == 200:
            data = r.json()
            oa = data.get("openAccessPdf")
            if oa and oa.get("url"):
                pr = _s.get(oa["url"], timeout=TIMEOUT)
                if pr.status_code == 200 and b'%PDF' in pr.content[:200]:
                    return pr.content, "S2"
    except: pass
    
    # CrossRef FT
    try:
        r = _s.get(f"https://api.crossref.org/works/{doi}", timeout=TIMEOUT)
        if r.status_code == 200:
            for link in r.json().get("message", {}).get("link", []):
                url = link.get("URL", "")
                try:
                    pr = _s.get(url, timeout=TIMEOUT)
                    if pr.status_code == 200 and b'%PDF' in pr.content[:200]:
                        return pr.content, "CrossRef"
                except: pass
    except: pass
    
    # Europe PMC
    try:
        r = _s.get(
            f"https://www.ebi.ac.uk/europepmc/api/search?query=DOI:{doi}&format=json",
            timeout=TIMEOUT
        )
        if r.status_code == 200:
            for result in r.json().get("resultList", {}).get("result", []):
                pmcid = result.get("pmcid", "")
                if pmcid and pmcid.startswith("PMC"):
                    pr = _s.get(f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/", timeout=TIMEOUT)
                    if pr.status_code == 200 and b'%PDF' in pr.content[:200]:
                        return pr.content, "PMC"
    except: pass
    
    return None, None

# REMAINING
REMAINING = [
    # Drynaria papers (priority!)
    ("044_Kandhasamy_2008_Drynaria_quercifolia", "10.13005/bbra/3104"),
    ("055_Mani_2023_comprehensive_review_Drynaria", "10.5530/phrev.2023.17.12"),
    ("073_Prasanna_2014_vitro_antimicrobial_Drynaria", "10.5958/0975-4385.2015.00002.3"),
    # MDPI
    ("006_Al-Khayri_2023_Plant_secondary_metabolites", "10.3390/metabo13060716"),
    ("014_Boulebd_2023_Exploring_antioxidant_properties", "10.3390/antiox12091669"),
    ("015_Bouyahya_2022_Mechanisms_anti_quorum_sensing", "10.3390/molecules27051484"),
    ("016_Cao_2025_Functional_dimorphism", "10.3390/metabo15120805"),
    ("019_Chang_2024_Epiphytic_patterns", "10.3390/metabo14080409"),
    ("023_DeRossi_2025_Antimicrobial_potential", "10.3390/antiox14020200"),
    ("034_Gulcin_2023_DPPH_radical_scavenging", "10.3390/pr11082248"),
    ("065_Nandhini_2022_MRSA_developments", "10.3390/antibiotics11050606"),
    ("067_Nikolaou_2023_Calcium_magnesium_fertilizer", "10.3390/agronomy13020482"),
    ("082_Salam_2023_Plant_metabolomics", "10.3390/life13030706"),
    ("086_Shamsudin_2022_Antibacterial_flavonoids", "10.3390/molecules27041149"),
    ("091_Sultana_2024_Investigating_flavonoids_HPTLC", "10.3390/molecules29215161"),
    ("096_Todorov_2023_Antioxidant_coumarins", "10.3390/ph16050651"),
    ("104_Yamauchi_2024_DPPH_structure_activity", "10.3390/antiox13030309"),
    # Other
    ("004_Aisha_2020_Bactericidal_antioxidant", "10.46545/aijbls.v2i1.213"),
    ("011_Bakri_2025_Antibacterial_activity", "10.35311/jmpi.v11i1.743"),
    ("020_Cronin_2025_Sociality_fern", "10.26686/wgtn.28308023"),
    ("021_Cruz_2017_Phytochemical_screening", "10.20944/preprints201908.0293.v1"),
    ("024_Deepa_2025_Phytochemistry_traditional", "10.69613/h20b8n73"),
    ("026_Divekar_2022_Plant_secondary_metabolites", "10.1007/978-3-031-51158-5_24"),
    ("033_Ghorbani_2025_Effect_drying_methods", "10.1186/s12870-025-06524-8"),
    ("039_Huang_2022_Biosynthesis_terpenoid", "10.3389/fpls.2021.729161"),
    ("048_Kumari_2024_Qualitative_quantitative", "10.1007/s42535-024-00961-w"),
    ("050_Lakkana_2024_Optimization_maceration", "10.1080/22311866.2024.2448019"),
    ("053_Liu_2022_Phenolic_profiles_antioxidant", "10.3389/fpls.2022.1037582"),
    ("054_Lubos_2011_identity_morphology_ferns", "10.7828/ajob.v2i1.91"),
    ("064_Naghavi_2024_Global_burden_AMR", "10.2139/ssrn.6712818"),
    ("070_Okabe_2024_Suppressed_distribution_protein", "10.1007/s00795-023-00379-4"),
    ("072_Platzer_2022_Radical_scavenging_phenolic", "10.3389/fnut.2022.882458"),
    ("080_Rodrigues_2023_Grape_pomace_phenolic", "10.1016/j.foodchem.2023.137780"),
    ("084_Senawong_2023_Impact_grinding_particle", "10.1155/2023/4512665"),
    ("092_Sun_2023_Therapeutic_phenolic_compounds", "10.5772/intechopen.99799"),
    ("095_Thulasi_2023_Comparative_pharmacognostical", "10.4103/jdras.jdras_168_22"),
    ("097_Viji_2013_Screening_antibacterial_medicinal", "10.1201/9781003100768-5"),
    ("098_Vojvodic_2023_Safety_assessment_herbal", "10.1016/j.jfca.2023.105483"),
    ("099_Wang_2024_Spatial_metabolomic", "10.3724/j.issn.1000-0518.2010.01.117121"),
    ("100_Wang_2025_Morphological_variability_Ecoli", "10.1186/s12879-025-10484-7"),
    ("103_Woumbo_2021_Valorization_Glycine_max", "10.1155/2021/4869909"),
]

os.makedirs(OUT, exist_ok=True)
print("=" * 70)
print("📚 v5 — curl_cffi browser fingerprint for MDPI + all sources")
print(f"   {len(REMAINING)} papers | {THREADS} threads")
print("=" * 70)

def process(fname, doi):
    fp = os.path.join(OUT, fname + ".pdf")
    if os.path.exists(fp) and os.path.getsize(fp) > 10000:
        return "exists", f"Already exists"
    
    # Determine if MDPI (needs curl)
    if '10.3390/' in doi:
        data, src = download_mdpi_curl(doi)
        if data:
            with open(fp, 'wb') as f: f.write(data)
            return "success", f"OK ({len(data)//1024}KB via {src})"
    
    # Try standard approaches
    data, src = download_other(doi)
    if data:
        with open(fp, 'wb') as f: f.write(data)
        return "success", f"OK ({len(data)//1024}KB via {src})"
    
    # MDPI that failed curl approach - try google cache
    if '10.3390/' in doi:
        try:
            suffix = doi.split('/')[-1]
            # Try google cache
            r = _s.get(f"https://webcache.googleusercontent.com/search?q=cache:{doi}", timeout=TIMEOUT)
            if r.status_code == 200 and b'%PDF' in r.content[:200]:
                with open(fp, 'wb') as f: f.write(r.content)
                return "success", f"OK via Google Cache"
        except: pass
    
    return "failed", f"Gagal total"

with ThreadPoolExecutor(max_workers=THREADS) as exe:
    futures = {exe.submit(process, f, d): (f, d) for f, d in REMAINING}
    success, failed, exists = [], [], []
    
    for i, future in enumerate(as_completed(futures)):
        fname, doi = futures[future]
        status, reason = future.result()
        icons = {"success": "✅", "exists": "⏭️", "failed": "❌"}
        tprint(f"  [{i+1:>2}/{len(REMAINING)}] {icons[status]} {fname[:55]}  {reason}")
        if status == "success": success.append(fname)
        elif status == "exists": exists.append(fname)
        else: failed.append((fname, doi))

print("\n" + "=" * 70)
print(f"📊 v5 FINAL: {len(success)}✅ {len(exists)}⏭️ {len(failed)}❌")
print("=" * 70)
if success:
    print(f"\n✅ BERHASIL:")
    for s in success: print(f"  {s}")
if failed:
    print(f"\n❌ TERSISA ({len(failed)}):")
    for f, d in failed: print(f"  {f}  — {d}")

# Generate final report
report_path = os.path.join(OUT, "REPORT_FINAL.md")
with open(report_path, 'w') as f:
    f.write("# 📚 Laporan Akhir Download Referensi\n\n")
    f.write(f"**Tanggal:** {__import__('time').strftime('%Y-%m-%d %H:%M')}\n\n")
    
    all_files = [fn for fn in os.listdir(OUT) if fn.endswith('.pdf')]
    f.write(f"**Total PDF di folder:** {len(all_files)}\n\n")
    
    f.write("## ✅ Berhasil Didownload\n\n")
    for fn in sorted(all_files):
        size = os.path.getsize(os.path.join(OUT, fn)) // 1024
        f.write(f"- {fn} ({size}KB)\n")
    
    f.write("\n## ❌ Gagal — Perlu Manual\n\n")
    for fn, doi in failed:
        f.write(f"- {doi} — {fn}\n")
    
    f.write("\n## 📋 Cara Download Manual\n\n")
    f.write("### MDPI Papers (Open Access - gratis)\n")
    f.write("1. Buka: https://www.mdpi.com/DOI_SUFFIX\n")
    f.write("2. Klik **Download PDF** (gratis, no login)\n")
    f.write("3. Simpan di folder yang sama\n\n")
    f.write("### Lainnya\n")
    f.write("1. Google Scholar: cari judul paper\n")
    f.write("2. Atau ResearchGate: cari author\n\n")

print(f"\n📄 Report: {report_path}")
print(f"📁 Folder: {OUT}")
