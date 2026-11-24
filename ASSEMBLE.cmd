@echo off
cd /d "%~dp0"
echo Assembling Windows CPU bundle. Please wait...
copy /b offline-parts\part001+offline-parts\part002+offline-parts\part003+offline-parts\part004+offline-parts\part005+offline-parts\part006+offline-parts\part007+offline-parts\part008+offline-parts\part009+offline-parts\part010+offline-parts\part011+offline-parts\part012 routeocr-win11-py311-cpu.zip
if errorlevel 1 goto failed
powershell -NoProfile -Command "if ((Get-FileHash -LiteralPath 'routeocr-win11-py311-cpu.zip' -Algorithm SHA256).Hash -ne '4b454d01817afe92ce9ba045ced70a9977a074fc2e1b188c42dccd790a37b452') { exit 1 }"
if errorlevel 1 goto failed
echo SHA256 OK. Extract routeocr-win11-py311-cpu.zip into a NEW folder and read README.md.
pause
exit /b 0
:failed
echo ERROR: download or assembly incomplete. Extract all downloaded branch ZIP files first.
pause
exit /b 1
