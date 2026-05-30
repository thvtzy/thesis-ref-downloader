#!/usr/bin/env python3
"""
v4.1 — Final push: Only the critical Drynaria + MDPI papers
Uses Semantic Scholar title search + PMC ID resolution + direct approaches
"""
import re, os, threading, json, time
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

OUT_DIR = r"D:\Skripsi_Referensi_PDF"
TIMEOUT = 30
THREADS = 3

_print_lock = threading.Lock()
def tprint(*args, **kwargs):
    with _print_lock:
        print(*args, **kwargs)

_s = requests.Session()
_s.headers.update({"User-Agent": "Mozilla/5.0"})

# ─── S2 TITLE SEARCH + DOWNLOAD ───
def s2_title_download(doi, title_hint=""):
    """Search Semantic Scholar by title first, then try to download."""
    try:
        # Use title from DOI suffix  
        query = title_hint or doi.split('/')[-1]
        # Make query more specific
        query = query.replace('_', ' ').replace('-', ' ')
        
        r = _s.get(
            f"https://api.semanticscholar.org/graph/v1/paper/search?query={requests.utils.quote(query)}&limit=3&fields=openAccessPdf,paperId,externalIds",
            timeout=TIMEOUT,
            headers={"Accept": "application/json"}
        )
        
        if r.status_code == 200:
            data = r.json()
            for paper in data.get("data", []):
                # Check if DOI matches
                ext_ids = paper.get("externalIds", {})
                paper_doi = ext_ids.get("DOI", "")
                if paper_doi and paper_doi == doi:
                    # Found matching paper
                    oa_pdf = paper.get("openAccessPdf", {})
                    if oa_pdf and oa_pdf.get("url"):
                        pr = _s.get(oa_pdf["url"], timeout=TIMEOUT)
                        if pr.status_code == 200 and b'%PDF' in pr.content[:200]:
                            return pr.content, "S2-Title"
                    
                    # Try S2 storage
                    pid = paper.get("paperId")
                    if pid:
                        for attempt in range(3):
                            pdf_url = f"https://pdfs.semanticscholar.org/{pid[:2]}/{pid[2:4]}/{pid}.pdf"
                            pr = _s.get(pdf_url, timeout=TIMEOUT)
                            if pr.status_code == 200 and b'%PDF' in pr.content[:200]:
                                return pr.content, "S2-PDF"
                            # Try different path formats
                            pdf_url2 = f"https://pdfs.semanticscholar.org/{pid[:4]}/{pid[4:8]}/{pid}.pdf"
                            pr = _s.get(pdf_url2, timeout=TIMEOUT)
                            if pr.status_code == 200 and b'%PDF' in pr.content[:200]:
                                return pr.content, "S2-PDF2"
                    break
                # If no DOI match, still try first result
                if not paper_doi:
                    oa_pdf = paper.get("openAccessPdf", {})
                    if oa_pdf and oa_pdf.get("url"):
                        pr = _s.get(oa_pdf["url"], timeout=TIMEOUT)
                        if pr.status_code == 200 and b'%PDF' in pr.content[:200]:
                            return pr.content, "S2-Fuzzy"
        return None, None
    except:
        return None, None

# ─── NCBI PMC ID via TITLE ───
def pmc_title_search(doi, title_hint=""):
    """Search PubMed by title, get PMC ID, download PDF."""
    try:
        query = title_hint.replace('_', ' ').replace('-', ' ')
        r = _s.get(
            f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pmc&term={requests.utils.quote(query)}&retmode=json&retmax=5",
            timeout=TIMEOUT
        )
        if r.status_code == 200:
            data = r.json()
            ids = data.get("esearchresult", {}).get("idlist", [])
            for pmc_id in ids:
                pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id}/pdf/main.pdf"
                pr = _s.get(pdf_url, timeout=TIMEOUT)
                if pr.status_code == 200 and b'%PDF' in pr.content[:200]:
                    return pr.content, "PMC-Title"
                
                pdf_url2 = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id}/pdf/"
                pr2 = _s.get(pdf_url2, timeout=TIMEOUT)
                if pr2.status_code == 200 and b'%PDF' in pr2.content[:200]:
                    return pr2.content, "PMC-Direct"
        return None, None
    except:
        return None, None

# ─── RESEARCHGATE SEARCH ───
def rg_search(doi, title_hint=""):
    """Search ResearchGate for PDF."""
    try:
        query = title_hint.replace('_', ' ').replace('-', ' ')
        r = _s.get(
            f"https://www.researchgate.net/search/publication?q={requests.utils.quote(query)}",
            timeout=TIMEOUT
        )
        if r.status_code == 200:
            # Try to find PDF links
            pdf_patterns = [
                r'href=["\'](https?://[^"\']+\.pdf)["\']',
                r'href=["\'](https?://[^"\']+/publication/[^"\']+)["\']',
            ]
            for pat in pdf_patterns:
                for m in re.finditer(pat, r.text):
                    url = m.group(1)
                    if 'pdf' in url.lower() or 'publication' in url:
                        try:
                            pr = _s.get(url, timeout=TIMEOUT)
                            if pr.status_code == 200 and b'%PDF' in pr.content[:200]:
                                return pr.content, "RG"
                        except: pass
        return None, None
    except:
        return None, None

# ─── DIRECT URL PATTERNS ───
def direct_patterns(doi, title_hint=""):
    """Try direct URL patterns."""
    try:
        suffix = doi.split('/')[-1]
        title_slug = title_hint.replace('_', '-').lower()[:60]
        author = title_hint.split('_')[0].lower() if title_hint else ""
        year = ""
        ym = re.search(r'(19|20)\d{2}', title_hint)
        if ym: year = ym.group()
        
        urls = set()
        # Generic patterns
        urls.add(f"https://arxiv.org/pdf/{suffix}.pdf")
        
        # Add DOI.org with various Accept headers
        headers_list = [
            {"Accept": "application/pdf"},
            {"Accept": "application/x-pdf"},
            {"Accept": "*/*"},
        ]
        for h in headers_list:
            try:
                r = _s.get(f"https://doi.org/{doi}", headers={**_s.headers, **h}, timeout=TIMEOUT, allow_redirects=True)
                if r.status_code == 200 and b'%PDF' in r.content[:200]:
                    return r.content, "DOI-Direct"
            except: pass
        
        return None, None
    except:
        return None, None

# ─── GOOGLE WEB LENS ───
def google_lens(doi, title_hint=""):
    """Search Google for the PDF."""
    try:
        query = f'"{doi}" pdf'
        r = _s.get(
            f"https://www.google.com/search?q={requests.utils.quote(query)}",
            timeout=TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        if r.status_code == 200:
            pdf_links = re.findall(r'href=["\'](https?://[^"\']+\.pdf)["\']', r.text)
            for url in pdf_links[:3]:
                try:
                    pr = _s.get(url, timeout=TIMEOUT)
                    if pr.status_code == 200 and b'%PDF' in pr.content[:200]:
                        return pr.content, "Google"
                except: pass
        return None, None
    except:
        return None, None


# ─── CRITICAL DOIs (Drynaria papers + MDPI) ───
CRITICAL = [
    # Drynaria quercifolia papers (MOST IMPORTANT!)
    ("044_Kandhasamy_2008_Drynaria_quercifolia_L_JSm_potential_anticancer", "10.13005/bbra/3104"),
    ("055_Mani_2023_comprehensive_review_Drynaria_quercifolia_L_botany", "10.5530/phrev.2023.17.12"),
    ("073_Prasanna_2014_vitro_antimicrobial_activity_Drynaria_quercifolia", "10.5958/0975-4385.2015.00002.3"),
    ("097_Viji_2013_Screening_antibacterial_activity_analysis_some_medicinal", "10.1201/9781003100768-5"),
    ("054_Lubos_2011_identity_morphology_three_species_fern_genera", "10.7828/ajob.v2i1.91"),
    ("065_Nandhini_2022_Recent_developments_methicillin_resistant_Staphylococcus", "10.3390/antibiotics11050606"),
    ("104_Yamauchi_2024_DPPH_measurements_structure_activity_relationship", "10.3390/antiox13030309"),
    ("034_Gulcin_2023_DPPH_radical_scavenging_assay", "10.3390/pr11082248"),
    # MDPI papers
    ("006_Al-Khayri_2023_Plant_secondary_metabolites", "10.3390/metabo13060716"),
    ("014_Boulebd_2023_Exploring_antioxidant_properties", "10.3390/antiox12091669"),
    ("015_Bouyahya_2022_Mechanisms_anti_quorum_sensing", "10.3390/molecules27051484"),
    ("016_Cao_2025_Functional_dimorphism_analysis", "10.3390/metabo15120805"),
    ("019_Chang_2024_Epiphytic_patterns_impacting", "10.3390/metabo14080409"),
    ("023_DeRossi_2025_Antimicrobial_potential_polyphenols", "10.3390/antiox14020200"),
    ("067_Nikolaou_2023_Calcium_magnesium_enriched_organic", "10.3390/agronomy13020482"),
    ("082_Salam_2023_Plant_metabolomics_overview", "10.3390/life13030706"),
    ("086_Shamsudin_2022_Antibacterial_effects_flavonoids", "10.3390/molecules27041149"),
    ("091_Sultana_2024_Investigating_flavonoids", "10.3390/molecules29215161"),
    ("096_Todorov_2023_Antioxidant_activity_coumarins", "10.3390/ph16050651"),
    # Other important ones
    ("080_Rodrigues_2023_Grape_pomace_natural_source", "10.1016/j.foodchem.2023.137780"),
    ("084_Senawong_2023_Impact_grinding_sorting", "10.1155/2023/4512665"),
    ("092_Sun_2023_Therapeutic_potential_phenolic", "10.5772/intechopen.99799"),
    ("098_Vojvodic_2023_Safety_assessment_herbal", "10.1016/j.jfca.2023.105483"),
    ("103_Woumbo_2021_Valorization_Glycine_max", "10.1155/2021/4869909"),
    ("099_Wang_2024_Spatial_metabolomic", "10.3724/j.issn.1000-0518.2010.01.117121"),
    # Small journals
    ("004_Aisha_2020_Bactericidal_antioxidant", "10.46545/aijbls.v2i1.213"),
    ("020_Cronin_2025_Sociality_terrestrial", "10.26686/wgtn.28308023"),
    ("021_Cruz_2017_Phytochemical_screening", "10.20944/preprints201908.0293.v1"),
    ("024_Deepa_2025_Phytochemistry_traditional", "10.69613/h20b8n73"),
    ("026_Divekar_2022_Plant_secondary_metabolites", "10.1007/978-3-031-51158-5_24"),
    ("048_Kumari_2024_Qualitative_quantitative", "10.1007/s42535-024-00961-w"),
    ("050_Lakkana_2024_Optimization_short_term", "10.1080/22311866.2024.2448019"),
    ("064_Naghavi_2024_Global_burden_bacterial", "10.2139/ssrn.6712818"),
    ("070_Okabe_2024_Suppressed_distribution", "10.1007/s00795-023-00379-4"),
    ("095_Thulasi_2023_Comparative_pharmacognostical", "10.4103/jdras.jdras_168_22"),
]

ALL_METHODS = [
    ("S2-Title", lambda d, t: s2_title_download(d, t)),
    ("RG", lambda d, t: rg_search(d, t)),
    ("Direct", lambda d, t: direct_patterns(d, t)),
    ("Google", lambda d, t: google_lens(d, t)),
    ("PMC", lambda d, t: pmc_title_search(d, t)),
]

os.makedirs(OUT_DIR, exist_ok=True)
total = len(CRITICAL)
success, failed = [], []

print("=" * 70)
print("📚 v4.1 — Final Push: Drynaria + MDPI special approach")
print(f"   {total} papers | {THREADS} threads")
print("=" * 70)

def process(fname, doi):
    fp = os.path.join(OUT_DIR, fname + ".pdf")
    if os.path.exists(fp) and os.path.getsize(fp) > 10000:
        return "exists", f"Already exists ({os.path.getsize(fp)//1024}KB)"
    
    # Try each method
    for mname, mfn in ALL_METHODS:
        try:
            data, src = mfn(doi, fname)
            if data:
                with open(fp, 'wb') as f:
                    f.write(data)
                return "success", f"OK ({len(data)//1024}KB via {mname}/{src})"
        except: pass
    
    return "failed", f"All methods failed: {doi}"

with ThreadPoolExecutor(max_workers=THREADS) as exe:
    futures = {exe.submit(process, f, d): (f, d) for f, d in CRITICAL}
    for i, future in enumerate(as_completed(futures)):
        fname, doi = futures[future]
        status, reason = future.result()
        icons = {"success": "✅", "exists": "⏭️", "failed": "❌"}
        tprint(f"  [{i+1:>2}/{total}] {icons[status]} {fname[:55]}  {reason}")
        if status == "success":
            success.append(fname)
        else:
            failed.append((fname, doi))

print("\n" + "=" * 70)
print(f"📊 FINAL v4.1: {len(success)}✅ baru / {len(failed)}❌ tersisa")
print("=" * 70)
if success:
    print(f"\n✅ BERHASIL:")
    for s in success:
        print(f"  {s}.pdf")
if failed:
    print(f"\n❌ TERSISA ({len(failed)}):")
    for f, d in failed:
        print(f"  {f}.pdf  — {d}")
print(f"\n📁 {OUT_DIR}")
