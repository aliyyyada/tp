@echo off
cd /d "%~dp0"
echo Assembling offline bundle...
copy /b offline-parts\part001+offline-parts\part002+offline-parts\part003+offline-parts\part004+offline-parts\part005 tp-offline-win11-py311.zip
if errorlevel 1 goto failed
powershell -NoProfile -Command "if ((Get-FileHash -LiteralPath 'tp-offline-win11-py311.zip' -Algorithm SHA256).Hash -ne '82dc434860884413f73cefdbd04df3552857de40c3fc2e82258a9164b1b1bdf1') { exit 1 }"
if errorlevel 1 goto failed
echo SHA256 OK. Extract tp-offline-win11-py311.zip and follow README.md inside.
pause
exit /b 0
:failed
echo ERROR: incomplete download or failed assembly.
pause
exit /b 1
