# Thesis Reference Downloader 🚀

**Ekstrak daftar referensi dari DOCX skripsi → cari DOI → download PDF dari 10+ sumber Open Access.**

## Cara Pakai

```bash
# 1. Install dependencies
pip install requests lxml

# 2. Download dari DOCX langsung
python v6_multi_source.py "D:\path\ke\skripsi.docx" --output "D:/PDFs"

# 3. Atau download DOI spesifik
python v6_multi_source.py --doi 10.3390/metabo14080409 10.3389/fpls.2021.729161

# 4. Atau dari file TXT berisi DOIs
python v6_multi_source.py --doi-file dofs.txt
```

## ✨ Fitur

| Fitur | Status |
|-------|--------|
| ⚡ Parallel download (multi-thread) | ✅ |
| 🌐 **10 sumber fallback otomatis** | ✅ |
| 🔄 Auto retry | ✅ |
| 🧠 Semantic Scholar API | ✅ |
| 🏛️ Europe PMC → MDPI papers via PMCID | ✅ |
| 🔗 CrossRef Full-Text | ✅ |
| 🔓 Unpaywall OA finder | ✅ |
| 📊 OpenAlex scholarly graph | ✅ |
| 🌍 Google Cache | ✅ |
| 📚 CORE aggregator + DOAJ | ✅ |
| 🧪 Direct URL guessing | ✅ |
| 📄 Auto-ekstrak DOI dari DOCX Daftar Pustaka | ✅ |

## ⚙️ Sumber Download (urutan prioritas)

1. **Semantic Scholar** — Best hit rate, OA PDF langsung
2. **Europe PMC** — Banyak MDPI papers tersedia sebagai PMCID
3. **CrossRef** — Link dari publisher langsung
4. **Unpaywall** — Best OA location finder
5. **OpenAlex** — Comprehensive scholarly graph API
6. **Google Cache** — PDF versi cache
7. **CORE API** — OA aggregator
8. **DOAJ** — Directory of Open Access Journals
9. **Direct URL** — Tebak URL berdasarkan publisher pattern
10. **Sci-Hub** — Last resort

## 📋 Publisher Support Matrix

| Publisher | DOI Prefix | Status |
|-----------|-----------|--------|
| MDPI | `10.3390/` | ⚠️ Akamai CDN → via PMC IDs
| Frontiers | `10.3389/` | ✅ Guaranteed OA via S2
| Springer/BMC | `10.1186/`, `10.1007/` | ✅ Mostly OA via Springer
| Hindawi/Wiley | `10.1155/` | ❌ Blocked (migrated to Wiley)
| Elsevier | `10.1016/` | ⚠️ Paywalled
| Taylor & Francis | `10.1080/` | ⚠️ Paywalled
| Preprints.org | `10.20944/` | ✅ Free
| Wiley | `10.1002/` | ⚠️ Mostly paywalled
| IntechOpen | `10.5772/` | ✅ OA langsung

## 📊 Hasil Download (Skripsi — Drynaria quercifolia)

| Status | Jumlah |
|--------|--------|
| ✅ Berhasil | **62 PDF** |
| ❌ Gagal (blocked / paywalled) | 34 |
| ⏭️ Jurnal Lokal (Google Scholar) | 17 |
| ⏭️ Buku Teks (Google Books) | 5 |

### MDPI Papers (15) — Tersedia di PubMed Central

13 dari 15 MDPI papers punya PMCID dan bisa di-download manual dari NCBI:

```
https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11356174/pdf/metabolites-14-00409.pdf
https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10302943/pdf/metabo-13-00716.pdf
... (lihat download_links.html untuk daftar lengkap)
```

Buka aja link di browser, gratis.

## 📁 Struktur File

```
├── v6_multi_source.py          ← Main downloader (10 sources)
├── extract_and_download_v2.py  ← v2 (parallel Sci-Hub)
├── extract_and_download_v3.py  ← v3 (multi-layer fallback)
├── retry_v4.py                 ← v4 (Semantic Scholar)
├── retry_v5.py                 ← v5 (curl_cffi)
├── requirements.txt
├── README.md
├── ROADMAP.md
└── download_links.html         ← Klik untuk download manual
```

## 📝 Requirements

- Python 3.8+
- `pip install requests lxml`
- (Opsional) `playwright` + `curl_cffi` untuk bypass lanjutan

## ⚠️ Limitations

- **MDPI (Akamai CDN)**: Bots 403 → tapi semua gratis di mdpi.com
- **Elsevier/Springer paywall**: Butuh akses institusi
- **Jurnal lokal Indo**: Google Scholar
- **Buku teks**: Google Books / perpustakaan

## 🚀 Roadmap

- [ ] **Automated PMC download** via Playwright/undetected-chromedriver
- [ ] **OCR for scanned PDFs** (metadata extraction)
- [ ] **GUI / Web interface**
- [ ] **Zotero integration**
- [ ] **Multi-language support** (title-based search)

---

> Dibuat untuk skripsi **"Bioprospeksi Drynaria quercifolia sebagai Antimikroba dan Antioksidan"**
> Universitas Mulawarman
