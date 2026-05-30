# Thesis Reference Downloader v2 🚀

Tool otomatis: ekstrak daftar referensi dari DOCX skripsi → cari DOI → download PDF dari Sci-Hub.

**v2 improvements:**
- ⚡ **Parallel download** (5 thread) — 3x-5x lebih cepet
- 🌐 **Multi-domain Sci-Hub** — auto fallback `.ru` → `.se` → `.st` → `.ee`
- 🔄 **Auto retry** — 3x percobaan kalo gagal
- 📊 **Progress bar real-time**
- ⏭️ **Resume** — udah pernah download gak perlu ulang

## Cara Pakai

```bash
# Install
pip install requests lxml

# Basic
python extract_and_download_v2.py "D:\path\ke\skripsi.docx"

# Custom output folder + thread count
python extract_and_download_v2.py "D:\path\ke\skripsi.docx" --output "D:/PDFs" --threads 5
```

## Output
```
D:\Skripsi_Referensi_PDF\
├── 001_Abubakar_2020_Preparation_medicinal_plants.pdf
├── 002_Agarwal_2022_Sensitivity_specificity.pdf
├── ...
├── download_log.txt
└── failed.txt
```

## File Structure
```
├── extract_and_download.py      ← v1 (single thread)
├── extract_and_download_v2.py   ← v2 (parallel, multi-domain, resume) ✅
├── README.md
├── ROADMAP.md
├── requirements.txt
└── .gitignore
```
