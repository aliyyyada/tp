@echo off
rem Run on an INTERNET-CONNECTED Windows PC with Python 3.11 x64.
cd /d "%~dp0\.."
if not exist gpu-wheels mkdir gpu-wheels
py -3.11 -m pip download --no-deps --only-binary=:all: --platform win_amd64 --python-version 311 --implementation cp --abi cp311 --index-url https://download.pytorch.org/whl/cu118 --dest gpu-wheels torch==2.5.1+cu118 torchvision==0.20.1+cu118
if errorlevel 1 exit /b 1
echo Copy gpu-wheels to the offline PC with the CPU bundle, then run tools\install_gpu_offline.cmd.
echo NVIDIA driver must support CUDA 11.8. GTX1070 is Pascal; avoid unverified newer CUDA/PyTorch builds.
pause
