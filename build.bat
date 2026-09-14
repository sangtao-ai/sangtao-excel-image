@echo off
chcp 65001 >nul
setlocal

rem Dong goi thanh mot file TaoAnh.exe chay duoc tren may khong cai Python.

cd /d "%~dp0"

echo.
echo ================================================================
echo   Dong goi TaoAnh.exe
echo ================================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo   Chua co moi truong ao. Dang tao...
    python -m venv .venv || goto :fail
)

set PY=.venv\Scripts\python.exe

echo   Cai thu vien...
%PY% -m pip install -q --upgrade pip
%PY% -m pip install -q -r requirements.txt || goto :fail
%PY% -m pip install -q pyinstaller || goto :fail

echo   Sinh file mau va huong dan...
%PY% -m pip install -q python-docx
%PY% tools\make_sample.py || goto :fail
%PY% tools\make_guide.py || goto :fail

echo   Dang dong goi (mat 1-2 phut)...
%PY% -m PyInstaller ^
    --onefile ^
    --console ^
    --name TaoAnh ^
    --clean ^
    --noconfirm ^
    --exclude-module tkinter ^
    --exclude-module PIL ^
    --exclude-module numpy ^
    --exclude-module pytest ^
    main.py || goto :fail

echo   Gom file phat hanh...
set OUT=release\TaoAnh
if exist "%OUT%" rmdir /s /q "%OUT%"
mkdir "%OUT%"

copy /y dist\TaoAnh.exe "%OUT%\" >nul
copy /y mau.xlsx "%OUT%\" >nul
copy /y HUONG-DAN.txt "%OUT%\" >nul 2>nul
copy /y HUONG-DAN.docx "%OUT%\" >nul 2>nul
copy /y "launcher\*.bat" "%OUT%\" >nul
copy /y "launcher\DOC FILE NAY TRUOC.txt" "%OUT%\" >nul

echo.
echo ================================================================
echo   Xong. Thu muc phat hanh: %OUT%
echo.
dir /b "%OUT%"
echo ================================================================
echo.
echo   Nen ca thu muc "%OUT%" thanh .zip roi dua len GitHub Releases.
echo   Hoac chay: gh release create v1.0.0 TaoAnh.zip
echo.
pause
exit /b 0

:fail
echo.
echo   Dong goi that bai. Xem loi o tren.
echo.
pause
exit /b 1
