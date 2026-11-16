@echo off
cd /d "%~dp0"
py -3.11 -c "import struct; assert struct.calcsize('P')==8" >nul 2>&1
if errorlevel 1 (
 echo Install Python 3.11 x64 from installers first.
 exit /b 1
)
py -3.11 -m venv .venv
if errorlevel 1 exit /b 1
.venv\Scripts\python -m pip install --no-index --find-links wheels -r requirements.txt
if errorlevel 1 exit /b 1
echo Install installers\tesseract.exe; keep extra language downloads disabled.
echo Models are already included in tessdata. See README.md.
