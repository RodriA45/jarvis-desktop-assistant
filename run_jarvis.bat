@echo off
setlocal EnableDelayedExpansion
title J.A.R.V.I.S - Sistema de Inteligencia Artificial

REM --- Configurar colores ANSI (Windows 10/11) ---
for /F %%a in ('"prompt $E$S & echo on & for %%b in (1) do rem"') do set "ESC=%%a"
set "CYAN=%ESC%[36m"
set "GREEN=%ESC%[32m"
set "YELLOW=%ESC%[33m"
set "RED=%ESC%[31m"
set "RESET=%ESC%[0m"

echo %CYAN%      __     _      ____   __     __  ___   ____  %RESET%
echo %CYAN%     / /    / \    ^|  _ \  \ \   / / ^|_ _^| / ___^| %RESET%
echo %CYAN%  _ / /    / _ \   ^| ^|_) ^|  \ \ / /   ^| ^|  \___ \ %RESET%
echo %CYAN% ^| ^|_^| ^|  / ___ \  ^|  _ ^<    \ V /    ^| ^|   ___) ^|%RESET%
echo %CYAN%  \___/  /_/   \_\ ^|_^| \_\    \_/    ^|___^| ^|____/ %RESET%
echo.
echo %CYAN%============================================================%RESET%
echo   %YELLOW%Inicializando Secuencia de Arranque%RESET%
echo %CYAN%============================================================%RESET%
echo.

REM 1. Verificar Python
echo %YELLOW%[1/3] Verificando entorno de Python...%RESET%
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo %RED%[ERROR] Python no esta instalado o no se encuentra en el PATH.%RESET%
    echo %RED%Por favor, instala Python 3.10+ desde https://python.org%RESET%
    pause
    exit /b 1
)

REM 2. Verificar e instalar dependencias desde requirements.txt
echo %YELLOW%[2/3] Validando modulos y dependencias...%RESET%
cd /d "%~dp0"
python -c "import webview, anthropic, psutil, pyautogui, edge_tts, pygame, requests, sounddevice, soundfile, numpy, whisper" >nul 2>&1
if %errorlevel% neq 0 (
    echo %RED%[INFO] Faltan librerias. Iniciando instalacion automatizada...%RESET%
    python -m pip install --upgrade pip --quiet
    echo %CYAN%Instalando dependencias desde requirements.txt...%RESET%
    python -m pip install -r requirements.txt --quiet
    if errorlevel 1 (
        echo %RED%[ERROR] Ocurrio un error al instalar las dependencias.%RESET%
        pause
        exit /b 1
    )
    echo %GREEN%[OK] Dependencias instaladas con exito.%RESET%
) else (
    echo %GREEN%[OK] Todas las dependencias estan listas.%RESET%
)

REM 3. Verificar servicios auxiliares (Ollama, ffmpeg)
echo %YELLOW%[3/3] Chequeando servicios y conexiones...%RESET%
where ollama >nul 2>&1
if %errorlevel% equ 0 (
    netstat -ano ^| findstr 11434 >nul 2>&1
    if errorlevel 1 (
        echo %CYAN%[INFO] Iniciando motor local de Ollama...%RESET%
        start /b ollama serve >nul 2>&1
    ) else (
        echo %GREEN%[OK] Ollama activo en puerto 11434.%RESET%
    )
) else (
    echo %YELLOW%[AVISO] Ollama no instalado. Usando IA remota o local basica.%RESET%
)

where ffmpeg >nul 2>&1
if %errorlevel% neq 0 (
    echo %RED%[AVISO] ffmpeg no detectado en el PATH de Windows.%RESET%
    echo %RED%El motor de escucha (Whisper) puede tener fallas.%RESET%
) else (
    echo %GREEN%[OK] Motor de transcodificacion ffmpeg disponible.%RESET%
)

echo.
echo %GREEN%============================================================%RESET%
echo %GREEN%  TODOS LOS SISTEMAS EN LINEA. INICIANDO INTERFAZ...%RESET%
echo %GREEN%============================================================%RESET%
echo.

python main.py

if %errorlevel% neq 0 (
    echo.
    echo %RED%[CRITICO] J.A.R.V.I.S ha finalizado de manera inesperada.%RESET%
    echo %RED%Por favor, revisa el error en la consola arriba.%RESET%
    pause
)
