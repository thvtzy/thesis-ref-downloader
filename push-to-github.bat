@echo off
title Push Thesis Ref Downloader to GitHub
echo ============================================
echo  Push ke GitHub - Thesis Ref Downloader
echo ============================================
echo.

:: Ask for token
set /p GITHUB_TOKEN="Masukkan GitHub Personal Access Token: "

:: Ask for repo name
set /p REPO_NAME="Nama repo (default: thesis-ref-downloader): "
if "%REPO_NAME%"=="" set REPO_NAME=thesis-ref-downloader

:: Ask for visibility
echo.
echo Pilih visibility:
echo  1. Public
echo  2. Private
set /p VIS="Pilihan [1/2]: "
if "%VIS%"=="2" (set PRIVATE=true) else (set PRIVATE=false)

:: Create repo via API
echo.
echo Membuat repo di GitHub...
curl -s -H "Authorization: token %GITHUB_TOKEN%" ^
  -H "Accept: application/vnd.github.v3+json" ^
  https://api.github.com/user/repos ^
  -d "{\"name\":\"%REPO_NAME%\",\"description\":\"Extract Daftar Pustaka from DOCX skripsi, find DOIs via CrossRef, download PDFs from Sci-Hub (parallel, multi-domain, auto-resume)\",\"private\":%PRIVATE%}" >nul

if %ERRORLEVEL% NEQ 0 (
  echo Gagal bikin repo. Cek token lu.
  pause
  exit /b
)

:: Set remote and push
echo.
echo Push ke GitHub...
cd /d "D:\thesis-ref-downloader"
git remote add origin "https://%GITHUB_TOKEN%@github.com/thvtzy/%REPO_NAME%.git"
git branch -M main
git push -u origin main

if %ERRORLEVEL% EQU 0 (
  echo.
  echo ============================================
  echo  ✅ BERHASIL!
  echo  https://github.com/thvtzy/%REPO_NAME%
  echo ============================================
) else (
  echo.
  echo ❌ Gagal push. Mungkin repo sudah ada atau token invalid.
)

pause
