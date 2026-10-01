@echo off
title AutoShorts Pipeline - 24/7 Monitor
chcp 65001 > nul
echo ========================================================
echo       AutoShorts Pipeline - Monitoramento Continuo 24/7
echo ========================================================
echo.
echo Pressione Ctrl+C para encerrar.
echo Iniciando scheduler...
echo.

:loop
python main.py run
echo.
echo [AVISO] O processo encerrou ou reiniciou. Reiniciando em 10 segundos...
timeout /t 10 /nobreak
goto loop
