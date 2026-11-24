@echo off
cd /d "%~dp0\.."
if not exist gpu-wheels (
 echo GPU wheels are not in the CPU archive. Run prepare_gpu_wheels.cmd on an online PC first.
 exit /b 1
)
.venv\Scripts\python -m pip install --no-index --find-links gpu-wheels --find-links wheels torch==2.5.1+cu118 torchvision==0.20.1+cu118
if errorlevel 1 exit /b 1
.venv\Scripts\python -m pip check
.venv\Scripts\python -c "import torch; print(torch.__version__); print('CUDA:',torch.cuda.is_available()); print(torch.cuda.get_arch_list()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'No usable CUDA GPU')"
pause
