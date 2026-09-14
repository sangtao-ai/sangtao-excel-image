@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Tao anh hang loat - sangtao.ai

echo.
echo  ================================================================
echo    TAO ANH HANG LOAT TU FILE EXCEL
echo  ================================================================
echo.

set "EXE=%~dp0TaoAnh.exe"

if not exist "%EXE%" (
    echo    Khong tim thay TaoAnh.exe trong thu muc nay.
    echo.
    echo    Ban da giai nen het file chua? Dung chay truc tiep tu
    echo    ben trong file .zip - hay giai nen ra mot thu muc truoc.
    echo.
    pause
    exit /b 1
)

rem Keo tha file Excel vao .bat thi dung luon file do.
if not "%~1"=="" (
    echo    File: %~nx1
    echo.
    "%EXE%" %*
    echo.
    pause
    exit /b
)

rem Khong keo tha thi de chuong trinh tu tim file trong thu muc.
"%EXE%"
