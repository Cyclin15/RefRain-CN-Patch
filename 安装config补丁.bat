@echo off
rem RefRain -prism memories- 汉化补丁: config.exe 汉化补丁器 (仅支持 V1.03.7, 需要 Python 3)
cd /d "%~dp0"
if not exist config.exe (
  echo [错误] 未找到 config.exe，请把本文件放到游戏根目录再运行。
  pause & exit /b 1
)
where python >nul 2>nul
if errorlevel 1 (
  echo [错误] 未找到 Python。config.exe 的汉化补丁需要 Python 3。
  echo 请从 https://www.python.org/ 安装并勾选 "Add python.exe to PATH" 后重新运行。
  echo 游戏本体的汉化不受影响，可跳过本步骤。
  pause & exit /b 1
)
python cn_config_patch.py
pause
