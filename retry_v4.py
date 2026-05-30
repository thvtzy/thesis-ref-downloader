#!/usr/bin/env python3
"""
v4 — Final approach: Semantic Scholar API + PMC + CrossRef + OA fulltext
"""
import re, os, threading, urllib.parse, json
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

# ─── 1. SEMANTIC SCHOLAR API ───
def s2_api(doi):
    """Semantic Scholar API - returns OA PDF links."""
    try:
        r = _s.get(
            f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=openAccessPdf,externalIds",
            timeout=TIMEOUT,
            headers={"Accept": "application/json"}
        )
        if r.status_code == 200:
            data = r.json()
            oa_pdf = data.get("openAccessPdf")
            if oa_pdf and oa_pdf.get("url"):
                pdf_url = oa_pdf["url"]
                pr = _s.get(pdf_url, timeout=TIMEOUT)
                if pr.status_code == 200 and b'%PDF' in pr.content[:200]:
                    return pr.content, "S2"
            
            # Try to get PDF from S2's own storage
            paper_id = data.get("paperId")
            if paper_id:
                pdf_url = f"https://pdfs.semanticscholar.org/{paper_id[:4]}/{paper_id[4:8]}/{paper_id}.pdf"
                pr = _s.get(pdf_url, timeout=TIMEOUT)
                if pr.status_code == 200 and b'%PDF' in pr.content[:200]:
                    return pr.content, "S2"
        return None, None
    except:
        return None, None

# ─── 2. PMC - EUROPE PMC API ───
def europmc(doi):
    """Europe PMC API - get PDF from PubMed Central."""
    try:
        r = _s.get(
            f"https://www.ebi.ac.uk/europepmc/api/search?query=DOI:{doi}&format=json&pageSize=1",
            timeout=TIMEOUT
        )
        if r.status_code == 200:
            data = r.json()
            results = data.get("resultList", {}).get("result", [])
            if results:
                pmcid = results[0].get("pmcid", "")
                if pmcid and pmcid.startswith("PMC"):
                    # Try direct PDF
                    pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/"
                    pr = _s.get(pdf_url, timeout=TIMEOUT)
                    if pr.status_code == 200 and b'%PDF' in pr.content[:200]:
                        return pr.content, "PMC"
                    
                    # Try main.pdf format
                    pdf_url2 = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/main.pdf"
                    pr2 = _s.get(pdf_url2, timeout=TIMEOUT)
                    if pr2.status_code == 200 and b'%PDF' in pr2.content[:200]:
                        return pr2.content, "PMC"
                    
                    # Try Europe PMC PDF
                    source = results[0].get("source", "")
                    id_val = results[0].get("id", "")
                    pdf_url3 = f"https://www.europepmc.org/articles/{pmcid}/pdf"
                    pr3 = _s.get(pdf_url3, timeout=TIMEOUT)
                    if pr3.status_code == 200 and b'%PDF' in pr3.content[:200]:
                        return pr3.content, "EPMC"
        return None, None
    except:
        return None, None

# ─── 3. CROSSREF FULL-TEXT LINKS ───
def crossref_ft(doi):
    """CrossRef API - get full-text URLs."""
    try:
        r = _s.get(
            f"https://api.crossref.org/works/{doi}",
            timeout=TIMEOUT,
            headers={"Accept": "application/json"}
        )
        if r.status_code == 200:
            data = r.json()
            msg = data.get("message", {})
            # Check for full-text URLs
            ft_links = []
            for link in msg.get("link", []):
                url = link.get("URL", "")
                ct = link.get("content-type", "")
                if "pdf" in ct or "pdf" in url:
                    ft_links.append(url)
            
            # Try license URLs
            for lic in msg.get("license", []):
                url = lic.get("URL", "")
                if url:
                    ft_links.append(url)
            
            for url in ft_links:
                try:
                    pr = _s.get(url, timeout=TIMEOUT)
                    if pr.status_code == 200 and b'%PDF' in pr.content[:200]:
                        return pr.content, "CrossRef"
                except: pass
        return None, None
    except:
        return None, None

# ─── 4. PUBMED ABSTRACT -> FULL TEXT ───
def pubmed_direct(doi):
    """Search PubMed and try to extract full text."""
    try:
        r = _s.get(
            f"https://pubmed.ncbi.nlm.nih.gov/?term={doi}",
            timeout=TIMEOUT
        )
        if r.status_code == 200:
            # Extract PMC ID from page
            pmc_m = re.search(r'/pmc/articles/(PMC\d+)', r.text)
            if pmc_m:
                pmcid = pmc_m.group(1)
                pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/"
                pr = _s.get(pdf_url, timeout=TIMEOUT)
                if pr.status_code == 200 and b'%PDF' in pr.content[:200]:
                    return pr.content, "PubMed-PMC"
        return None, None
    except:
        return None, None

# ─── 5. HAL ARCHIVE OUVERTS (French OA) ───
def hal_archive(doi):
    """Search HAL Open Archives."""
    try:
        r = _s.get(f"https://api.archives-ouvertes.fr/search/?q=doi_s:{doi}&fl=file_s&wt=json",
                  timeout=TIMEOUT)
        if r.status_code == 200:
            data = r.json()
            docs = data.get("response", {}).get("docs", [])
            for doc in docs:
                files = doc.get("file_s", [])
                for f in files:
                    if f.endswith(".pdf"):
                        pr = _s.get(f, timeout=TIMEOUT)
                        if pr.status_code == 200 and b'%PDF' in pr.content[:200]:
                            return pr.content, "HAL"
        return None, None
    except:
        return None, None

# ─── 6. OPENAIRE (EU OA) ───
def openaire(doi):
    """OpenAIRE search for OA PDF."""
    try:
        r = _s.get(
            f"https://api.openaire.eu/search/publications?doi={doi}&format=json",
            timeout=TIMEOUT
        )
        if r.status_code == 200:
            data = r.json()
            results = data.get("response", {}).get("results", {}).get("result", [])
            for res in results:
                metadata = res.get("metadata", {}).get("oaf:entity", {}).get("oaf:result", {})
                # Try to find PDF link
                children = metadata.get("children", {}).get("instance", [])
                if not isinstance(children, list):
                    children = [children]
                for child in children:
                    web_loc = child.get("webLocation", [])
                    if not isinstance(web_loc, list):
                        web_loc = [web_loc]
                    for wl in web_loc:
                        url = wl.get("$", "")
                        if url and url.endswith(".pdf"):
                            pr = _s.get(url, timeout=TIMEOUT)
                            if pr.status_code == 200 and b'%PDF' in pr.content[:200]:
                                return pr.content, "OpenAIRE"
        return None, None
    except:
        return None, None

# ─── 7. GOOGLE WEB CACHE ───
def google_cache(doi):
    """Try to find PDF via Google cache."""
    try:
        r = _s.get(
            f"https://webcache.googleusercontent.com/search?q=cache:{doi}+pdf",
            timeout=TIMEOUT
        )
        if b'%PDF' in r.content[:200]:
            return r.content, "GoogleCache"
        return None, None
    except:
        return None, None

# ─── ALL COMBINED ───
ALL = [
    ("Semantic Scholar", s2_api),
    ("Europe PMC", europmc),
    ("CrossRef FT", crossref_ft),
    ("PubMed", pubmed_direct),
    ("HAL", hal_archive),
    ("OpenAIRE", openaire),
    ("Google Cache", google_cache),
]

def download_v4(doi):
    for name, fn in ALL:
        try:
            data, src = fn(doi)
            if data:
                return data, name
        except:
            continue
    return None, None


# Target DOIs - the 41 MDPI/others that failed
FAILED = {
    "006_Al-Khayri_2023_Plant_secondary_metabolites": "10.3390/metabo13060716",
    "014_Boulebd_2023_Exploring_antioxidant_properties": "10.3390/antiox12091669",
    "015_Bouyahya_2022_Mechanisms_anti-quorum-sensing": "10.3390/molecules27051484",
    "016_Cao_2025_Functional_dimorphism_analysis": "10.3390/metabo15120805",
    "019_Chang_2024_Epiphytic_patterns_impacting": "10.3390/metabo14080409",
    "023_DeRossi_2025_Antimicrobial_potential": "10.3390/antiox14020200",
    "026_Divekar_2022_Plant_secondary_metabolites": "10.1007/978-3-031-51158-5_24",
    "033_Ghorbani_2025_Effect_drying_methods": "10.1186/s12870-025-06524-8",
    "034_Gulcin_2023_DPPH_radical_scavenging": "10.3390/pr11082248",
    "039_Huang_2022_Biosynthesis_investigations": "10.3389/fpls.2021.729161",
    "048_Kumari_2024_Qualitative_quantitative": "10.1007/s42535-024-00961-w",
    "050_Lakkana_2024_Optimization_short-term": "10.1080/22311866.2024.2448019",
    "053_Liu_2022_Phenolic_profiles_antioxidant": "10.3389/fpls.2022.1037582",
    "055_Mani_2023_comprehensive_review_Drynaria": "10.5530/phrev.2023.17.12",
    "064_Naghavi_2024_Global_burden_bacterial": "10.2139/ssrn.6712818",
    "065_Nandhini_2022_Recent_developments": "10.3390/antibiotics11050606",
    "067_Nikolaou_2023_Calcium_magnesium": "10.3390/agronomy13020482",
    "070_Okabe_2024_Suppressed_distribution": "10.1007/s00795-023-00379-4",
    "072_Platzer_2022_Radical_scavenging": "10.3389/fnut.2022.882458",
    "082_Salam_2023_Plant_metabolomics_overview": "10.3390/life13030706",
    "080_Rodrigues_2023_Grape_pomace_natural": "10.1016/j.foodchem.2023.137780",
    "084_Senawong_2023_Impact_grinding_sorting": "10.1155/2023/4512665",
    "086_Shamsudin_2022_Antibacterial_effects": "10.3390/molecules27041149",
    "091_Sultana_2024_Investigating_flavonoids": "10.3390/molecules29215161",
    "092_Sun_2023_Therapeutic_potential": "10.5772/intechopen.99799",
    "095_Thulasi_2023_Comparative": "10.4103/jdras.jdras_168_22",
    "096_Todorov_2023_Antioxidant_activity": "10.3390/ph16050651",
    "098_Vojvodic_2023_Safety_assessment": "10.1016/j.jfca.2023.105483",
    "099_Wang_2024_Spatial_metabolomic": "10.3724/j.issn.1000-0518.2010.01.117121",
    "100_Wang_2025_Morphological_variability": "10.1186/s12879-025-10484-7",
    "103_Woumbo_2021_Valorization_Glycine": "10.1155/2021/4869909",
    "104_Yamauchi_2024_DPPH_measurements": "10.3390/antiox13030309",
    "004_Aisha_2020_Bactericidal_antioxidant": "10.46545/aijbls.v2i1.213",
    "011_Bakri_2025_Antibacterial_activity_test": "10.35311/jmpi.v11i1.743",
    "020_Cronin_2025_Sociality_terrestrial": "10.26686/wgtn.28308023",
    "021_Cruz_2017_Phytochemical_screening": "10.20944/preprints201908.0293.v1",
    "024_Deepa_2025_Phytochemistry_traditional": "10.69613/h20b8n73",
    "044_Kandhasamy_2008_Drynaria_quercifolia": "10.13005/bbra/3104",
    "054_Lubos_2011_identity_morphology": "10.7828/ajob.v2i1.91",
    "073_Prasanna_2014_vitro_antimicrobial": "10.5958/0975-4385.2015.00002.3",
    "097_Viji_2013_Screening_antibacterial": "10.1201/9781003100768-5",
}

os.makedirs(OUT_DIR, exist_ok=True)

print("=" * 70)
print("📚 v4 — Semantic Scholar + PMC + CrossRef + HAL + OpenAIRE")
print(f"   {len(FAILED)} papers | {THREADS} threads")
print("=" * 70)

success, failed = [], []

def process(fname, doi):
    fp = os.path.join(OUT_DIR, fname + ".pdf")
    if os.path.exists(fp) and os.path.getsize(fp) > 10000:
        return "exists", f"Already exists"
    
    data, src = download_v4(doi)
    if data:
        with open(fp, 'wb') as f:
            f.write(data)
        return "success", f"OK ({len(data)//1024}KB via {src})"
    return "failed", f"All failed: {doi}"

total = len(FAILED)
with ThreadPoolExecutor(max_workers=THREADS) as exe:
    futures = {exe.submit(process, f, d): (f, d) for f, d in FAILED.items()}
    for i, future in enumerate(as_completed(futures)):
        fname, doi = futures[future]
        status, reason = future.result()
        if status == "success":
            success.append(fname)
        else:
            failed.append((fname, doi))
        icons = {"success": "✅", "exists": "⏭️", "failed": "❌"}
        tprint(f"  [{i+1:>2}/{total}] {icons[status]} {fname[:50]}  {reason}")

print("\n" + "=" * 70)
print(f"📊 FINAL: {len(success)}✅ baru / {len(failed)}❌ masih gagal")
print("=" * 70)
if success:
    print(f"\n✅ BERHASIL ({len(success)}):")
    for s in success:
        print(f"  {s}.pdf")
if failed:
    print(f"\n❌ TERSISA ({len(failed)}):")
    for f, d in failed:
        print(f"  {f}.pdf  — {d}")
print(f"\n📁 {OUT_DIR}")
