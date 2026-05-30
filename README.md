# Thesis Reference Downloader 🚀

**Extract references from a DOCX thesis → find DOIs via CrossRef → download PDFs from 10+ Open Access sources with automatic fallback.**

## Quick Start

```bash
# 1. Install
pip install requests lxml

# 2. Download from your thesis DOCX
python v6_multi_source.py "skripsi.docx" --output "./PDFs"

# 3. Or download specific DOIs
python v6_multi_source.py --doi 10.3390/metabo14080409 10.3389/fpls.2021.729161

# 4. Or from a text file with one DOI per line
python v6_multi_source.py --doi-file dofs.txt
```

## Features

| Feature | Status |
|---------|--------|
| ⚡ Parallel multi-thread download | ✅ |
| 🌐 **10 Open Access sources** with automatic fallback | ✅ |
| 🔄 Auto-retry | ✅ |
| 📄 Auto-extract DOIs from DOCX bibliography | ✅ |
| 🏆 Semantic Scholar API (best hit rate) | ✅ |
| 🏛️ Europe PMC → MDPI papers via PMCID | ✅ |
| 🔗 CrossRef Full-Text | ✅ |
| 🔓 Unpaywall OA finder | ✅ |
| 📊 OpenAlex scholarly graph | ✅ |
| 🌍 Google Cache | ✅ |
| 📚 CORE + DOAJ aggregators | ✅ |
| 🧪 Direct URL guessing by publisher pattern | ✅ |
| 🏴‍☠️ Sci-Hub fallback | ✅ |

## Source Pipeline

Sources are tried **in order** for each DOI. The first one to return a valid PDF wins.

| # | Source | Best For | Limits |
|---|--------|----------|--------|
| 1 | **Semantic Scholar** | Open Access papers (Frontiers, Hindawi, misc) | No API key needed |
| 2 | **Europe PMC** | **MDPI bypass!** Papers indexed in PubMed Central | NCBI rate-limits requests |
| 3 | **CrossRef** | Publisher direct links | Many publishers block bots |
| 4 | **Unpaywall** | Hidden OA papers | Requires email (any) |
| 5 | **OpenAlex** | Comprehensive scholarly graph | None |
| 6 | **Google Cache** | Cached PDFs | Hit-or-miss |
| 7 | **CORE** | OA aggregator (200M+ papers) | None |
| 8 | **DOAJ** | Directory of Open Access Journals | Limited coverage |
| 9 | **Direct URL** | Known publisher URL patterns | Publisher-dependent |
| 10 | **Sci-Hub** | Paywalled papers | Domains change frequently |

## Publisher Support

| Publisher | DOI Prefix | Direct Download | Notes |
|-----------|-----------|----------------|-------|
| **MDPI** | `10.3390/` | ⚠️ Via PMC ID | Akamai CDN blocks bots, but papers are in PubMed Central |
| **Frontiers** | `10.3389/` | ✅ Semantic Scholar | Guaranteed Open Access |
| **Springer / BMC** | `10.1186/`, `10.1007/` | ✅ Mostly via Direct URL | Most BMC papers are OA |
| **Elsevier** | `10.1016/` | ❌ | Usually paywalled |
| **Taylor & Francis** | `10.1080/` | ❌ | Usually paywalled |
| **Wiley** | `10.1002/`, `10.1155/` | ❌ | Paywalled / blocked |
| **IntechOpen** | `10.5772/` | ✅ | Open Access |
| **Preprints.org** | `10.20944/` | ✅ | Free |
| **SSRN** | `10.2139/` | ⚠️ | Sometimes blocked |

## Project Structure

```
├── v6_multi_source.py          ← Main downloader (10 sources, 1 script)
├── extract_and_download_v2.py  ← v2 (parallel Sci-Hub)
├── extract_and_download_v3.py  ← v3 (multi-layer fallback)
├── retry_v4.py / v5.py         ← v4-v5 (Semantic Scholar + curl_cffi)
├── requirements.txt
├── README.md
└── ROADMAP.md
```

## Requirements

- Python 3.8+
- `pip install requests lxml`
- (Optional) `playwright` + `undetected-chromedriver` for advanced bot bypass

## Limitations

- **MDPI (Akamai CDN)**: PDF URLs are blocked for bots — but all papers are free to download manually from mdpi.com
- **Paywalled publishers** (Elsevier, Springer non-OA, T&F): Need institutional access
- **Small/obscure journals**: May not be indexed in any of the 10 sources
- **Books & local journals**: Try Google Scholar or Google Books

## Roadmap

- [ ] Automated PMC download via undetected-chromedriver
- [ ] GUI / web interface
- [ ] Zotero / reference manager integration
- [ ] Title-based search for papers without DOIs
- [ ] Language-agnostic bibliography extraction

---

MIT License. Contributions welcome!
