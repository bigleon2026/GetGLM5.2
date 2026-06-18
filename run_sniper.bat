@echo off
REM GLM 抢购 cron 包装脚本
REM 在抢购前关闭 Chrome（避免 profile 锁），然后启动抢购

echo [%date% %time%] GLM Sniper cron trigger

REM 关闭 Chrome（避免 profile 被锁）
taskkill /F /IM chrome.exe 2>nul
timeout /t 2 /nobreak >nul

REM 运行抢购
cd /d F:\Git\GetGLM5.2
python glm_sniper.py --time "%TARGET_TIME%"

echo [%date% %time%] GLM Sniper finished
