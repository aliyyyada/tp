@echo off
cd /d "%~dp0"
echo Assembling Windows CPU bundle. Please wait...
copy /b offline-parts\part001+offline-parts\part002+offline-parts\part003+offline-parts\part004+offline-parts\part005+offline-parts\part006+offline-parts\part007+offline-parts\part008+offline-parts\part009+offline-parts\part010+offline-parts\part011+offline-parts\part012 routeocr-win11-py311-cpu.zip
if errorlevel 1 goto failed
powershell -NoProfile -Command "if ((Get-FileHash -LiteralPath 'routeocr-win11-py311-cpu.zip' -Algorithm SHA256).Hash -ne '3edf839881cb012f00352e921bad65f5e50261f48a0d45536b0db2f75782c98b') { exit 1 }"
if errorlevel 1 goto failed
echo SHA256 OK. Extract routeocr-win11-py311-cpu.zip into a NEW folder and read README.md.
pause
exit /b 0
:failed
echo ERROR: download or assembly incomplete. Extract all downloaded branch ZIP files first.
pause
exit /b 1
