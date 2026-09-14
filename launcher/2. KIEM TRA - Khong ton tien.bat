@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Kiem tra file Excel - khong tao anh

echo.
echo  ================================================================
echo    KIEM TRA FILE EXCEL
echo  ================================================================
echo.
echo    Lenh nay chi kiem tra file cua ban dien dung chua:
echo      - Dong nao thieu prompt
echo      - Duong dan anh tham chieu co dung khong
echo.
echo    KHONG tao anh. KHONG tru tien. KHONG can API key.
echo.
echo    Nen chay cai nay truoc khi tao file vai tram dong.
echo.
echo  ----------------------------------------------------------------
echo.

set "EXE=%~dp0TaoAnh.exe"

if not exist "%EXE%" (
    echo    Khong tim thay TaoAnh.exe trong thu muc nay.
    echo    Hay giai nen het file ra mot thu muc roi chay lai.
    echo.
    pause
    exit /b 1
)

if not "%~1"=="" (
    "%EXE%" %1 --dry-run
) else (
    "%EXE%" --dry-run
)

echo.
pause
