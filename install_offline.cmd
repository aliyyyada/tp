@echo off
cd /d "%~dp0"
py -3.11 -c "import struct; assert struct.calcsize('P')==8" >nul 2>&1
if errorlevel 1 (
 echo Install Python 3.11 x64 from installers first. Enable Python Launcher.
 pause
 exit /b 1
)
py -3.11 -m venv .venv
if errorlevel 1 goto failed
.venv\Scripts\python -m pip install --no-index --find-links wheels -r requirements-win-cpu.lock
if errorlevel 1 goto failed
.venv\Scripts\python -m pip check
if errorlevel 1 goto failed
.venv\Scripts\python -c "import torch,torchvision,easyocr,cv2,fitz,openpyxl; print('Imports OK; torch',torch.__version__)"
if errorlevel 1 goto failed
echo Installed CPU package. See README.md for commands.
pause
exit /b 0
:failed
echo Installation failed. See error above. If a DLL is missing, install installers\vc_redist.x64.exe.
pause
exit /b 1
