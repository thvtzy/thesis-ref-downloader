#!/usr/bin/env python3
"""Runner for v3 — Python handles the path, not bash."""
import sys, subprocess, os

docx = r"D:\Documents\01_KULIAH & SKRIPSI\01_SKRIPSI_THESIS\B_Draft_Bimbingan\skripsi 5.3\SKRIPSI M FARIZ A - 5.5.docx"

v3_path = r"D:\thesis-ref-downloader\extract_and_download_v3.py"

result = subprocess.run(
    [sys.executable, v3_path, docx, "--threads", "5"],
    capture_output=True, text=True, timeout=600
)
print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr[:2000])
print(f"EXIT CODE: {result.returncode}")
