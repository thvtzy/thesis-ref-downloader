# Thesis Reference Downloader 🚀

Tool otomatis: ekstrak daftar referensi dari DOCX skripsi → cari DOI → download PDF dari berbagai sumber **open access**.

## Fitur

| Fitur | Status |
|-------|--------|
| ⚡ Parallel download (5 thread) | ✅ |
| 🌐 Multi-source fallback (Sci-Hub, CrossRef, Semantic Scholar, Unpaywall, PMC, CORE, dll) | ✅ |
| 🔄 Auto retry + resume | ✅ |
| 🕷️ Cloudflare bypass (cloudscraper) | ✅ |
| 🧪 Browser TLS fingerprint (curl_cffi) | ✅ |
| 📊 Progress bar + summary | ✅ |
| 📄 Auto-laporan failed references | ✅ |

## Cara Pakai

```bash
# Install dependencies
pip install requests lxml cloudscraper curl_cffi

# v2 — Langsung download dari Sci-Hub (parallel)
python extract_and_download_v2.py "D:\path\ke\skripsi.docx"

# v3 — Multi-layer fallback: Sci-Hub → CrossRef → Unpaywall → Scholar
python extract_and_download_v3.py "D:\path\ke\skripsi.docx"

# Custom folder + thread
python extract_and_download_v2.py "D:\path\ke\skripsi.docx" --output "D:/PDFs" --threads 5
```

## Hasil Download (Skripsi — Drynaria quercifolia)

| Status | Jumlah |
|--------|--------|
| ✅ Berhasil | **46 PDF (70MB)** |
| ❌ Gagal (Akamai CDN / DOI not found) | 34 |
| ⏭️ Jurnal Lokal (cari di Google Scholar) | 17 |
| ⏭️ Buku Teks (cari di Google Books/Perpus) | 5 |

**Sumber download terbanyak:**
1. 🏆 **Semantic Scholar API** — OA PDF langsung
2. **Sci-Hub** — jurnal lama (pre-2021) 
3. **CrossRef Full-Text** — publisher direct
4. **OSF / PMC** — open repositories

> ⚠️ **MDPI papers (Akamai CDN)** gak bisa di-download otomatis. Tapi semuanya **Open Access gratis** — buka aja `https://www.mdpi.com/<doi-suffix>` terus klik **Download PDF**.

## File Script

```
├── extract_and_download.py        ← v1 (single thread)
├── extract_and_download_v2.py     ← v2 (parallel, multi-domain, resume) ✅
├── extract_and_download_v3.py     ← v3 (multi-layer: Sci-Hub→CrossRef→Unpaywall→Scholar)
├── retry_v31.py                   ← v3.1 (MDPI direct resolver)
├── retry_v32.py                   ← v3.2 (Cloudflare bypass via cloudscraper)
├── retry_v33.py                   ← v3.3 (Unpaywall API + CORE + LibGen)
├── retry_v4.py                    ← v4 (Semantic Scholar + PMC + HAL + OpenAIRE)
├── retry_v41.py                   ← v4.1 (Title-based S2 search + Google)
├── retry_v5.py                    ← v5 (curl_cffi browser TLS fingerprint)
├── dedup.py                       ← Bersihin duplikat PDF by content hash
├── run_v3.py                      ← Runner helper (handle Windows path spasi)
├── requirements.txt
├── README.md
├── ROADMAP.md
├── .gitignore
└── push-to-github.bat
```

## Output Folder

```
D:\Skripsi_Referensi_PDF\
├── 046_Khan_2007_Isolation_antibacterial_Drynaria.pdf
├── 060_Mithraja_2012_Antibacterial_Drynaria_quercifolia.pdf
├── 083_Scherer_2009_Antioxidant_activity_index_AAI.pdf
├── ... (46 PDF total)
├── REPORT_FINAL.md
├── download_log.txt
└── failed.txt
```
