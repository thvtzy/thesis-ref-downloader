# Thesis Ref Downloader — Roadmap Improvement

## 🎯 Fase 1: Core Stabilization ✅
| # | Improvement | Status |
|---|-------------|--------|
| 1 | **Multi-domain Sci-Hub fallback** | ✅ `.ru` → `.se` → `.st` → `.ee` |
| 2 | **Retry logic** | ✅ 3x exponential backoff |
| 3 | **Config file (YAML/JSON)** | ⏳ Next |

## 🚀 Fase 2: Smarter Searching
| # | Improvement | Kenapa |
|---|-------------|--------|
| 4 | **Google Scholar scraping fallback** | CrossRef DOI gak selalu dapet → coba cari di Google Scholar pake title+author |
| 5 | **Unpaywall / Open Access API** | Banyak jurnal OA yg gratis tanpa Sci-Hub (Unpaywall punya database 47M+ artikel) |
| 6 | **Core.ac.uk / CORE API** | Repositori open access — alternatif kalo Sci-Hub gak punya |
| 7 | **Deteksi DOI dari teks** | Banyak referensi udah cantumin DOI di entry-nya → ambil langsung, skip CrossRef |

## 🔧 Fase 3: User Experience ✅
| # | Improvement | Status |
|---|-------------|--------|
| 8 | **Progress bar (tqdm)** | ✅ Real-time per-file status + counter |
| 9 | **Resume capability** | ✅ Skip existing files |
| 10 | **Parallel download (3-5 threads)** | ✅ ThreadPoolExecutor 5 threads |
| 11 | **Manual URL input** | ⏳ Next |

## 📁 Fase 4: Management & Report
| # | Improvement | Kenapa |
|---|-------------|--------|
| 12 | **Export CSV/Excel rekap** | Biar lu bisa liat "mana yg udah, mana yg belum" di Excel |
| 13 | **GitHub-style table report** | Output HTML keren yg bisa dibuka di browser |
| 14 | **Duplicate checker** | Cek apakah PDF yg udah ada di folder cocok dengan referensi lain (beda entry tapi paper sama) |
| 15 | **Bulk rename tool** | Kalo user udah punya PDF tapi namanya berantakan → tinggal taruh di folder, di-scan, di-rename otomatis |

## 🧠 Fase 5: Advanced
| # | Improvement | Kenapa |
|---|-------------|--------|
| 16 | **GUI sederhana (tkinter/streamlit)** | Biar yg gak mau pake CLI bisa pake tombol doang |
| 17 | **Cache DOI database** | CrossRef punya rate limit ketat. Cache lokal biar cepet + gak kena blok |
| 18 | **Smart author matching** | Skrg masih string match — banyak false positive "Author mismatch" karena beda format nama |
| 19 | **Deteksi otomatis jurnal lokal** | Pake daftar jurnal Indonesia + regex pola (Jurnal Ilmiah, Jurnal of dll) |

## 📊 Estimasi Dampak
Improvement      | Dampak | Effort
-----------------|--------|-------
Fase 1 (1-3)     | ⭐⭐⭐  | ⏱ 1-2 jam
Fase 2 (4-7)     | ⭐⭐⭐⭐ | ⏱ 3-5 jam
Fase 3 (8-11)    | ⭐⭐⭐  | ⏱ 2-3 jam
Fase 4 (12-15)   | ⭐⭐   | ⏱ 2-4 jam
Fase 5 (16-19)   | ⭐⭐⭐⭐ | ⏱ 5-10 jam

## Prioritas gue kalo lu gas sekarang

1. **Parallel download** — paling gede impactnya. 107 ref bisa selesai 2-3 menit bukan 10 menit
2. **Unpaywall API** — gratis, legal, many journals available
3. **Resume + progress bar** — biar enak dipake
