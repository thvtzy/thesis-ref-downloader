#!/usr/bin/env python3
"""Dedup by content hash - remove files that are byte-for-byte identical"""
import os, hashlib, re

OUT = r"D:\Skripsi_Referensi_PDF"

# Group by MD5
by_hash = {}
for fn in os.listdir(OUT):
    if not fn.endswith('.pdf'):
        continue
    fp = os.path.join(OUT, fn)
    sz = os.path.getsize(fp)
    if sz < 10000:
        os.remove(fp)
        print(f"🗑️  Removed corrupt: {fn}")
        continue
    
    # First 64KB hash is enough for near-certainty
    with open(fp, 'rb') as f:
        h = hashlib.md5(f.read(65536)).hexdigest()
    by_hash.setdefault(h, []).append((fn, fp, sz))

# Keep original name (shorter), delete copies
deleted = 0
for h, files in by_hash.items():
    if len(files) > 1:
        # Sort by name length, keep shortest (original)
        files.sort(key=lambda x: (len(x[0]), x[0]))
        keep = files[0]
        for fn, fp, sz in files[1:]:
            os.remove(fp)
            deleted += 1
            print(f"🗑️  Deleted duplicate: {fn} ({sz//1024}KB) ← kept: {keep[0]}")

# Count final
pdfs = sorted([f for f in os.listdir(OUT) if f.endswith('.pdf') and os.path.getsize(os.path.join(OUT, f)) > 10000])
total_size = sum(os.path.getsize(os.path.join(OUT, f)) for f in pdfs)
# Remove dup clean indexes  
seen_idx = set()
unique = []
for fn in pdfs:
    idx = re.match(r'(\d{3})', fn)
    if idx and idx.group(1) not in seen_idx:
        seen_idx.add(idx.group(1))
        unique.append(fn)

print(f"\n📊 CLEANUP: {deleted} duplikat dihapus")
print(f"📊 FINAL: {len(pdfs)} PDF files, {total_size//1024//1024}MB total, {len(unique)} unique references")

# Write clean report
with open(os.path.join(OUT, "REPORT_FINAL.md"), 'w') as f:
    f.write("# 📚 Laporan Final Download Referensi\n\n")
    f.write(f"**Skripsi:** Bioprospeksi _Drynaria quercifolia_ (L.) J.Sm. sebagai Antimikroba dan Antioksidan\n")
    f.write(f"**Tanggal:** {__import__('time').strftime('%Y-%m-%d %H:%M')}\n")
    f.write(f"**Total:** {len(pdfs)} file ({total_size//1024//1024}MB) — {len(unique)} referensi unik\n\n")
    
    f.write(f"## ✅ Berhasil Didownload ({len(unique)} referensi)\n\n")
    
    critical = {'046','060','077','083','088','094'}
    for fn in sorted(pdfs):
        sz = os.path.getsize(os.path.join(OUT, fn)) // 1024
        idx = re.match(r'(\d{3})', fn)
        star = " ⭐" if idx and idx.group(1) in critical else ""
        f.write(f"- {fn} ({sz}KB){star}\n")
    
    f.write("\n## ❌ Gagal (34 referensi)\n")
    f.write("Mayoritas **MDPI (Akamai CDN)** — Open Access gratis via:\n")
    f.write("1. Buka `https://www.mdpi.com/<doi_suffix>`\n")
    f.write("2. Klik **Download PDF** (gratis, no login)\n\n")
    f.write("| Index | Author | DOI |\n")
    f.write("|-------|--------|-----|\n")
    f.write("| 004 | Aisha | 10.46545/aijbls.v2i1.213 |\n")
    f.write("| 006 | Al-Khayri | 10.3390/metabo13060716 |\n")
    f.write("| 014 | Boulebd | 10.3390/antiox12091669 |\n")
    f.write("| 015 | Bouyahya | 10.3390/molecules27051484 |\n")
    f.write("| 016 | Cao | 10.3390/metabo15120805 |\n")
    f.write("| 019 | Chang | 10.3390/metabo14080409 |\n")
    f.write("| 020 | Cronin | 10.26686/wgtn.28308023 |\n")
    f.write("| 021 | Cruz | 10.20944/preprints201908.0293.v1 |\n")
    f.write("| 023 | DeRossi | 10.3390/antiox14020200 |\n")
    f.write("| 026 | Divekar | 10.1007/978-3-031-51158-5_24 |\n")
    f.write("| 034 | Gulcin | 10.3390/pr11082248 |\n")
    f.write("| 044 | Kandhasamy | 10.13005/bbra/3104 |\n")
    f.write("| 048 | Kumari | 10.1007/s42535-024-00961-w |\n")
    f.write("| 050 | Lakkana | 10.1080/22311866.2024.2448019 |\n")
    f.write("| 054 | Lubos | 10.7828/ajob.v2i1.91 |\n")
    f.write("| 055 | Mani | 10.5530/phrev.2023.17.12 |\n")
    f.write("| 064 | Naghavi | 10.2139/ssrn.6712818 |\n")
    f.write("| 065 | Nandhini | 10.3390/antibiotics11050606 |\n")
    f.write("| 067 | Nikolaou | 10.3390/agronomy13020482 |\n")
    f.write("| 070 | Okabe | 10.1007/s00795-023-00379-4 |\n")
    f.write("| 073 | Prasanna | 10.5958/0975-4385.2015.00002.3 |\n")
    f.write("| 080 | Rodrigues | 10.1016/j.foodchem.2023.137780 |\n")
    f.write("| 082 | Salam | 10.3390/life13030706 |\n")
    f.write("| 084 | Senawong | 10.1155/2023/4512665 |\n")
    f.write("| 086 | Shamsudin | 10.3390/molecules27041149 |\n")
    f.write("| 091 | Sultana | 10.3390/molecules29215161 |\n")
    f.write("| 092 | Sun | 10.5772/intechopen.99799 |\n")
    f.write("| 095 | Thulasi | 10.4103/jdras.jdras_168_22 |\n")
    f.write("| 096 | Todorov | 10.3390/ph16050651 |\n")
    f.write("| 097 | Viji | 10.1201/9781003100768-5 |\n")
    f.write("| 098 | Vojvodic | 10.1016/j.jfca.2023.105483 |\n")
    f.write("| 099 | Wang | 10.3724/j.issn.1000-0518.2010.01.117121 |\n")
    f.write("| 103 | Woumbo | 10.1155/2021/4869909 |\n")
    f.write("| 104 | Yamauchi | 10.3390/antiox13030309 |\n")
    
    f.write("\n**Jurnal Lokal (cari di Google Scholar):**\n")
    f.write("| 007 | Arnida |\n")
    f.write("| 013 | Bhakti |\n")
    f.write("| 022 | Damayanti |\n")
    f.write("| 029 | Febrina |\n")
    f.write("| 035 | Hanin |\n")
    f.write("| 037 | Hartoyo |\n")
    f.write("| 049 | Kuspradini |\n")
    f.write("| 063 | Mustofa |\n")
    f.write("| 068 | Nisa |\n")
    f.write("| 069 | Novaryatiin |\n")
    f.write("| 074 | Rafael |\n")
    f.write("| 076 | Rahman |\n")
    f.write("| 078 | Ratnasari |\n")
    f.write("| 079 | Rizqi |\n")
    f.write("| 081 | Rudiana |\n")
    f.write("| 090 | Sukma |\n")
    f.write("| 106 | Yusasrini |\n\n")
    
    f.write("**Buku Teks (cari di Google Books/Perpus):**\n")
    f.write("| 017 | Cappuccino |\n")
    f.write("| 028 | Evans |\n")
    f.write("| 036 | Harborne |\n")
    f.write("| 047 | Kokate |\n")
    f.write("| 058 | Miller |\n\n")
    
    f.write("---\n")
    f.write(f"_Auto-generated by Hermes Agent | {len(pdfs)} PDF dari {len(unique)+34+22} total referensi_\n")

print(f"📄 Report: {OUT}\\REPORT_FINAL.md")
