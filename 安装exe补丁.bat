@echo off
rem RefRain -prism memories- 汉化补丁: 主程序 1 字节补丁器 (仅支持 V1.03.7)
cd /d "%~dp0"
if not exist RefRain.exe (
  echo [错误] 未找到 RefRain.exe，请把本文件放到游戏根目录再运行。
  pause & exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "$b=[System.IO.File]::ReadAllBytes('RefRain.exe');" ^
 "if($b.Length -ne 1118160){ Write-Host '[错误] RefRain.exe 大小不符 (仅支持 V1.03.7, 1118160 字节)。'; exit 1 };" ^
 "if($b[0x67c2c] -eq 0x86){ Write-Host '[提示] 主程序已经打过补丁，无需重复操作。'; exit 0 };" ^
 "if($b[0x67c2c] -ne 0x80){ Write-Host '[错误] 字节特征不符 (仅支持 V1.03.7 原版主程序)。'; exit 1 };" ^
 "Copy-Item 'RefRain.exe' 'RefRain.exe.bak' -Force;" ^
 "$b[0x67c2c]=0x86;" ^
 "[System.IO.File]::WriteAllBytes('RefRain.exe',$b);" ^
 "Write-Host '[成功] 原版已备份为 RefRain.exe.bak，主程序补丁完成。'"
pause
