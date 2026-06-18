@echo off
title Enecel Dashboard & ETL Server
echo ==============================================
echo Iniciando Servidor Enecel Dashboard...
echo ==============================================
echo.
echo [1/2] Verificando e instalando dependencias (requirements.txt)...
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo [ERRO] Falha ao instalar dependencias do Python.
    pause
    exit /b %errorlevel%
)
echo.
echo [2/2] Abrindo o Dashboard no seu navegador (com depuração remota ativa)...
start chrome "http://localhost:5000" --remote-debugging-port=9222
echo.
echo Iniciando o servidor Flask em http://localhost:5000...
echo Mantenha esta janela aberta para manter o servidor rodando.
echo Pressione Ctrl+C para encerrar.
echo.
python app.py
pause
