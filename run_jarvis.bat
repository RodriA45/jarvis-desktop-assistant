@echo off
title J.A.R.V.I.S - Asistente de IA

echo ============================================================
echo   J.A.R.V.I.S - Asistente de IA
echo ============================================================
echo.

REM Verificar Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python no esta instalado o no se encuentra en el PATH.
    echo Por favor, instala Python 3.10+ desde https://python.org
    echo y asegurate de marcar la casilla "Add Python to PATH".
    pause
    exit /b 1
)

REM Verificar si las dependencias clave estan instaladas
echo [1/3] Verificando dependencias necesarias...
python -c "import webview, anthropic, requests, psutil, pyautogui, pyttsx3, sounddevice, soundfile, numpy, pycaw, comtypes, whisper" >nul 2>&1
if %errorlevel% equ 0 goto :dependencies_ok

echo [INFO] Se detectaron dependencias faltantes. Iniciando instalacion automatizada...
echo.
echo Actualizando pip...
python -m pip install --upgrade pip --quiet

echo Instalando librerias principales...
python -m pip install anthropic pywebview psutil pyautogui pyttsx3 duckduckgo-search SpeechRecognition requests soundfile numpy sounddevice openai-whisper pycaw comtypes pvporcupine --quiet
if errorlevel 1 (
    echo [ERROR] Ocurrio un error al instalar las dependencias.
    pause
    exit /b 1
)
echo [OK] Dependencias instaladas con exito!
echo.

:dependencies_ok
echo [OK] Todas las dependencias estan listas.

REM Verificar si Ollama esta instalado y si esta corriendo (puerto 11434)
where ollama >nul 2>&1
if %errorlevel% equ 0 (
    netstat -ano | findstr 11434 >nul 2>&1
    if errorlevel 1 (
        echo [2/3] Iniciando Ollama local en segundo plano...
        start /b ollama serve >nul 2>&1
    ) else (
        echo [2/3] Ollama ya se encuentra en ejecucion.
    )
) else (
    echo [2/3] Ollama no esta instalado - se omitio el auto-arranque.
)

REM Verificar ffmpeg (opcional pero recomendado para Whisper)
where ffmpeg >nul 2>&1
if %errorlevel% neq 0 (
    echo [AVISO] ffmpeg no encontrado en el PATH de Windows.
    echo         El procesamiento de voz STT podria tardar o fallar.
)

echo.
echo [3/3] Iniciando J.A.R.V.I.S...
echo ============================================================
echo.

cd /d "%~dp0"
python main.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Jarvis finalizo con error. Revisa la consola.
    pause
)
