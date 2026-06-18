@echo off
REM GLM 抢购包装脚本 - 关 Chrome → 跑抢购
echo [%date% %time%] GLM Sniper start

REM 关 Chrome 释放 profile
taskkill /F /IM chrome.exe 2>nul
timeout /t 3 /nobreak >nul

REM 跑抢购（从 config 读时间）
cd /d F:\Git\GetGLM5.2
python glm_sniper.py

echo [%date% %time%] GLM Sniper done
