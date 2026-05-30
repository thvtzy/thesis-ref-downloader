#!/usr/bin/env python3
"""
v3.1 — Retry GAGAL with MDPI direct resolver + better fallbacks
Only processes previously failed DOIs.
"""
import re, os, sys, time, json, zipfile, threading, urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
import requests

OUT_DIR = r"D:\Skripsi_Referensi_PDF"
TIMEOUT = 30
MAX_RETRIES = 3
THREADS = 5

_session = requests.Session()
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
})
_print_lock = threading.Lock()
def tprint(*args, **kwargs):
    with _print_lock:
        print(*args, **kwargs)

# ─── MDPI RESOLVER (Open Access — no paywall) ───
def download_mdpi(doi):
    """MDPI papers are Open Access — PDF is freely downloadable."""
    try:
        # Parse DOI: 10.3390/journal-volume-article
        parts = doi.split('/')
        if len(parts) < 2:
            return None, None
        suffix = parts[1]  # e.g. "metabo13060716" or "metabo-13-00716"
        
        # Try various MDPI PDF URL patterns
        patterns = []
        
        # Pattern 1: mdpi-res.com d_attachment (most common)
        # journal name is the alpha prefix
        m = re.match(r'([a-z]+)', suffix)
        if m:
            journal = m.group(1)
            patterns.append(f"https://mdpi-res.com/d_attachment/{journal}/{suffix}/{suffix}.pdf")
            patterns.append(f"https://mdpi-res.com/{journal}/{suffix}/{suffix}.pdf")
            patterns.append(f"https://mdpi-res.com/{journal}/{suffix}.pdf")
            patterns.append(f"https://www.mdpi.com/{journal}/{suffix}/pdf")
            patterns.append(f"https://www.mdpi.com/{journal}/{suffix}/pdf-vor")
        
        # Pattern 2: Try with hyphen format
        suffix_hyphen = suffix.replace('-', '')
        patterns.append(f"https://mdpi-res.com/d_attachment/{journal}/{suffix_hyphen}/{suffix_hyphen}.pdf")
        
        # Pattern 3: Direct mdpi.com
        patterns.append(f"https://www.mdpi.com/{suffix}/pdf")
        
        for url in patterns:
            try:
                resp = _session.get(url, timeout=TIMEOUT)
                if resp.status_code == 200 and b'%PDF' in resp.content[:200]:
                    return resp.content, "MDPI"
            except:
                continue
        
        return None, None
    except Exception as e:
        return None, None

# ─── FRONTIERS RESOLVER (Open Access) ───
def download_frontiers(doi):
    try:
        parts = doi.split('/')
        if len(parts) < 2:
            return None, None
        suffix = parts[1]
        url = f"https://www.frontiersin.org/journals/articles/{suffix}/pdf"
        resp = _session.get(url, timeout=TIMEOUT)
        if resp.status_code == 200 and b'%PDF' in resp.content[:200]:
            return resp.content, "Frontiers"
        return None, None
    except:
        return None, None

# ─── PUBMED CENTRAL RESOLVER ───
def download_pubmed_central(doi):
    try:
        # Try to find PMCID from DOI first
        r = _session.get(
            f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pmc&term={doi}&retmode=json",
            timeout=TIMEOUT
        )
        if r.status_code == 200:
            data = r.json()
            ids = data.get("esearchresult", {}).get("idlist", [])
            if ids:
                pmc_id = ids[0]
                pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id}/pdf/"
                resp = _session.get(pdf_url, timeout=TIMEOUT)
                if resp.status_code == 200 and b'%PDF' in resp.content[:200]:
                    return resp.content, "PMC"
        return None, None
    except:
        return None, None

# ─── RESEARCHGATE RESOLVER ───
def download_researchgate(doi):
    """Search ResearchGate for PDF."""
    try:
        # Search RG
        r = _session.get(
            f"https://www.researchgate.net/search/publication?q={doi}",
            timeout=TIMEOUT
        )
        if r.status_code == 200:
            # Find PDF links
            pdf_urls = re.findall(r'href=["\'](https?://[^"\']+\.pdf)["\']', r.text)
            for url in pdf_urls[:3]:
                try:
                    resp = _session.get(url, timeout=TIMEOUT)
                    if resp.status_code == 200 and b'%PDF' in resp.content[:200]:
                        return resp.content, "RG"
                except:
                    continue
        return None, None
    except:
        return None, None

# ─── OSFPREPRINTS RESOLVER ───
def download_osf(doi):
    """OSF preprints"""
    try:
        # osf.io/XXXXX → direct download
        parts = doi.split('/')
        if len(parts) >= 2:
            code = parts[-1].strip()
            url = f"https://osf.io/download/{code}/"
            resp = _session.get(url, timeout=TIMEOUT)
            if resp.status_code == 200 and b'%PDF' in resp.content[:200]:
                return resp.content, "OSF"
        return None, None
    except:
        return None, None

# ─── CORE.AC.UK RESOLVER (aggregator) ───
def download_core(doi):
    """CORE aggregator — UK open access."""
    try:
        url = f"https://core.ac.uk/api/direct/doi/{doi}"
        resp = _session.get(url, timeout=TIMEOUT)
        if resp.status_code == 200 and b'%PDF' in resp.content[:200]:
            return resp.content, "CORE"
        return None, None
    except:
        return None, None

# ─── DIRECT DOI.GOV DOWNLOAD ───
def download_doigov(doi):
    """Try doi.gov with different accept headers."""
    try:
        headers = {
            "Accept": "application/pdf, */*",
            "User-Agent": "Mozilla/5.0"
        }
        r = _session.get(f"https://doi.org/{doi}", headers=headers, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code == 200 and b'%PDF' in r.content[:200]:
            return r.content, "doi.org"
        return None, None
    except:
        return None, None

# ─── ALL-IN-ONE RESOLVER ───
def download_pdf_v3_1(doi):
    """Try ALL methods for a given DOI."""
    resolvers = [
        ("MDPI", download_mdpi),
        ("Frontiers", download_frontiers),
        ("PubMed Central", download_pubmed_central),
        ("CORE", download_core),
        ("doi.org", download_doigov),
        ("ResearchGate", download_researchgate),
        ("OSF", download_osf),
    ]
    
    for name, resolver in resolvers:
        try:
            pdf_data, source = resolver(doi)
            if pdf_data:
                return pdf_data, name
        except:
            continue
    
    return None, None


# ─── MAIN ───
FAILED_DOIS = [
    ("001_Abubakar_2020_Preparation_medicinal_plants_basic_extraction", ""),
    ("004_Aisha_2020_Bactericidal_antioxidant_activity_silico_analysis", "10.46545/aijbls.v2i1.213"),
    ("006_Al-Khayri_2023_Plant_secondary_metabolites_weapons_biotic", "10.3390/metabo13060716"),
    ("009_Bai_2025_Design_synthesis_antibacterial_activity_mechanism", "10.1002/cbdv.202402034"),
    ("011_Bakri_2025_Antibacterial_activity_test_extract_fraction", "10.35311/jmpi.v11i1.743"),
    ("012_Baliyan_2022_Determination_antioxidants_DPPH_radical_scavenging", "10.3390/molecules27041326"),
    ("014_Boulebd_2023_Exploring_antioxidant_properties_caffeoylquinic_feruloylquin", "10.3390/antiox12091669"),
    ("015_Bouyahya_2022_Mechanisms_anti-quorum-sensing_actions_clinical_trials", "10.3390/molecules27051484"),
    ("016_Cao_2025_Functional_dimorphism_analysis_sporotrophophyll_leaves", "10.3390/metabo15120805"),
    ("019_Chang_2024_Epiphytic_patterns_impacting_metabolite_diversity", "10.3390/metabo14080409"),
    ("020_Cronin_2025_Sociality_terrestrial_epiphytic_fern_Platycerium", "10.26686/wgtn.28308023"),
    ("021_Cruz_2017_Phytochemical_screening_antioxidant_anti-inflammatory_activi", "10.20944/preprints201908.0293.v1"),
    ("023_De%20Rossi_2025_Antimicrobial_potential_polyphenols_mechanisms_action", "10.3390/antiox14020200"),
    ("024_Deepa_2025_Phytochemistry_traditional_applications_therapeutic_properti", "10.69613/h20b8n73"),
    ("026_Divekar_2022_Plant_secondary_metabolites_defense_tools", "10.1007/978-3-031-51158-5_24"),
    ("027_Erb_2020_Plant_secondary_metabolites_defenses_regulators", "10.31219/osf.io/6ba7r"),
    ("031_Festus_2024_Quantitative_qualitative_phytochemical_analysis_ethanol", "10.30574/wjarr.2024.22.2.1149"),
    ("033_Ghorbani_2025_Effect_drying_methods_mucilage_anthocyanin", "10.1186/s12870-025-06524-8"),
    ("034_Gulcin_2023_DPPH_radical_scavenging_assay_Processes", "10.3390/pr11082248"),
    ("039_Huang_2022_Biosynthesis_investigations_terpenoid_alkaloid_flavonoid", "10.3389/fpls.2021.729161"),
    ("040_Jegan_2025_Phytochemical_screening_anti_inflammatory_activity", "10.13005/bbra/3367"),
    ("041_Joshi_2020_Evaluation_antioxidant_activity_some_medicinal", "10.5530/pj.2021.13.75"),
    ("044_Kandhasamy_2008_Drynaria_quercifolia_L_JSm_potential", "10.13005/bbra/3104"),
    ("048_Kumari_2024_Qualitative_quantitative_vitro_antioxidant_activity", "10.1007/s42535-024-00961-w"),
    ("050_Lakkana_2024_Optimization_short-term_dynamic_static_maceration", "10.1080/22311866.2024.2448019"),
    ("053_Liu_2022_Phenolic_profiles_antioxidant_activity_different", "10.3389/fpls.2022.1037582"),
    ("054_Lubos_2011_identity_morphology_three_species", "10.7828/ajob.v2i1.91"),
    ("055_Mani_2023_comprehensive_review_Drynaria_quercifolia_L", "10.5530/phrev.2023.17.12"),
    ("057_Mehganathan_2022_review_extraction_bioactive_compounds", "10.26420/austinchemeng.2022.1090"),
    ("064_Naghavi_2024_Global_burden_bacterial_antimicrobial_resistance", "10.2139/ssrn.6712818"),
    ("065_Nandhini_2022_Recent_developments_methicillin-resistant_Staphylococcus_aur", "10.3390/antibiotics11050606"),
    ("067_Nikolaou_2023_Calcium-_magnesium-enriched_organic_fertilizer_plant", "10.3390/agronomy13020482"),
    ("070_Okabe_2024_Suppressed_distribution_protein_surface", "10.1007/s00795-023-00379-4"),
    ("072_Platzer_2022_Radical_scavenging_mechanisms_phenolic_compounds", "10.3389/fnut.2022.882458"),
    ("073_Prasanna_2014_vitro_antimicrobial_activity_Drynaria_quercifolia", "10.5958/0975-4385.2015.00002.3"),
    ("080_Rodrigues_2023_Grape_pomace_natural_source_phenolic", "10.1016/j.foodchem.2023.137780"),
    ("082_Salam_2023_Plant_metabolomics_overview_role", "10.3390/life13030706"),
    ("084_Senawong_2023_Impact_grinding_sorting_particle_size", "10.1155/2023/4512665"),
    ("085_Shaikh_2020_Qualitative_tests_preliminary_phytochemical_screening", "10.22271/chemi.2020.v8.i2i.8834"),
    ("086_Shamsudin_2022_Antibacterial_effects_flavonoids_structure-activity_relation", "10.3390/molecules27041149"),
    ("089_Sujin_2021_Phytochemical_pharmacological_studies_oak_leaf", ""),
    ("091_Sultana_2024_Investigating_flavonoids_HPTLC_analysis_using", "10.3390/molecules29215161"),
    ("092_Sun_2023_Therapeutic_potential_phenolic_compounds_medicinal", "10.5772/intechopen.99799"),
    ("093_Sureshkumar_2026_Chemical_profiling_proximate_composition_antibacterial", ""),
    ("095_Thulasi_2023_Comparative_pharmacognostical_phytochemical_high-performance", "10.4103/jdras.jdras_168_22"),
    ("096_Todorov_2023_Antioxidant_activity_coumarins_metal_complexes", "10.3390/ph16050651"),
    ("097_Viji_2013_Screening_antibacterial_activity_analysis_some", "10.1201/9781003100768-5"),
    ("098_Vojvodić_2023_Safety_assessment_herbal_food_supplements", "10.1016/j.jfca.2023.105483"),
    ("099_Wang_2024_Spatial_metabolomic_profiling_Pinelliae_Rhizoma", "10.3724/j.issn.1000-0518.2010.01.117121"),
    ("100_Wang_2025_Morphological_variability_Escherichia_coli_colonizing", "10.1186/s12879-025-10484-7"),
    ("103_Woumbo_2021_Valorization_Glycine_max_Soybean_seed", "10.1155/2021/4869909"),
    ("104_Yamauchi_2024_DPPH_measurements_structure-activity_relationship_studies", "10.3390/antiox13030309"),
]

os.makedirs(OUT_DIR, exist_ok=True)

print("=" * 70)
print("📚 THESIS REF DOWNLOADER v3.1 — Retry GAGAL")
print(f"   MDPI direct resolver + PMC + CORE + OA sources")
print(f"   ⚡ {THREADS} threads")
print("=" * 70)

success = []
failed = []
no_doi = []

def process(fname, doi):
    filepath = os.path.join(OUT_DIR, fname + ".pdf")
    
    # Skip if already exists
    if os.path.exists(filepath) and os.path.getsize(filepath) > 10000:
        return "exists", f"Already exists ({os.path.getsize(filepath)//1024}KB)"
    
    if not doi:
        return "no_doi", "No DOI available"
    
    pdf_data, source = download_pdf_v3_1(doi)
    if pdf_data:
        with open(filepath, 'wb') as f:
            f.write(pdf_data)
        return "success", f"OK ({len(pdf_data)//1024}KB via {source})"
    else:
        return "failed", f"All OA sources failed: {doi}"

with ThreadPoolExecutor(max_workers=THREADS) as executor:
    futures = {executor.submit(process, fname, doi): (fname, doi) for fname, doi in FAILED_DOIS}
    
    done = 0
    total = len(FAILED_DOIS)
    for future in as_completed(futures):
        fname, doi = futures[future]
        done += 1
        try:
            status, reason = future.result()
            icons = {"success": "✅", "exists": "⏭️", "failed": "❌", "no_doi": "⚠️"}
            tprint(f"  [{done:>2}/{total}] {icons.get(status, '?')} {fname}.pdf  {reason}")
            if status == "success":
                success.append(fname)
            elif status == "no_doi":
                no_doi.append(fname)
            else:
                failed.append(fname)
        except Exception as e:
            tprint(f"  [{done:>2}/{total}] ❌ {fname}.pdf  Error: {str(e)[:60]}")
            failed.append(fname)

print("\n" + "=" * 70)
print(f"📊 HASIL RETRY: {len(success)} ✅ baru / {len(failed)} ❌ / {len(no_doi)} ⚠️ no DOI")
print("=" * 70)
if success:
    print(f"\n✅ BERHASIL ({len(success)}):")
    for s in success:
        print(f"  {s}.pdf")
if failed:
    print(f"\n❌ MASIH GAGAL ({len(failed)}):")
    for f in failed:
        print(f"  {f}.pdf")
if no_doi:
    print(f"\n⚠️  NO DOI ({len(no_doi)}):")
    for n in no_doi:
        print(f"  {n}.pdf")
print(f"\n📁 Folder: {OUT_DIR}")
