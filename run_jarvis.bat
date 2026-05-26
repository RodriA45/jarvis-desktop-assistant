@echo off
chcp 65001 >nul
title J.A.R.V.I.S — Asistente de IA

echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║             J.A.R.V.I.S — Sistema Híbrido            ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

:: Verificar Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python no está instalado o no se encuentra en el PATH.
    echo Por favor, instala Python 3.10+ desde https://python.org
    echo y asegúrate de marcar la casilla "Add Python to PATH".
    pause
    exit /b 1
)

:: Verificar si las dependencias clave están instaladas
echo [1/3] Verificando dependencias necesarias...
python -c "import webview, anthropic, requests, psutil, pyautogui, pyttsx3, sounddevice, soundfile, numpy, pycaw, comtypes, whisper" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Se detectaron dependencias faltantes. Iniciando instalación automatizada...
    echo.
    echo Actualizando pip...
    python -m pip install --upgrade pip --quiet
    
    echo Instalando librerías principales...
    pip install anthropic pywebview psutil pyautogui pyttsx3 duckduckgo-search SpeechRecognition requests soundfile numpy sounddevice openai-whisper pycaw comtypes pvporcupine --quiet
    
    if %errorlevel% neq 0 (
        echo [ERROR] Ocurrió un error al instalar las dependencias.
        pause
        exit /b 1
    )
    echo [OK] Dependencias instaladas con éxito!
    echo.
) else (
    echo [OK] Todas las dependencias están listas.
)

:: Verificar si Ollama está instalado y si está corriendo (puerto 11434)
where ollama >nul 2>&1
if %errorlevel% equ 0 (
    netstat -ano | findstr 11434 >nul 2>&1
    if errorlevel 1 (
        echo [2/3] Iniciando Ollama local en segundo plano...
        start /b ollama serve >nul 2>&1
    ) else (
        echo [2/3] Ollama ya se encuentra en ejecución.
    )
) else (
    echo [2/3] Ollama no está instalado (se omitió el auto-arranque).
)

:: Verificar ffmpeg (opcional pero recomendado para Whisper)
where ffmpeg >nul 2>&1
if %errorlevel% neq 0 (
    echo [AVISO] ffmpeg no encontrado en el PATH de Windows.
    echo         El procesamiento de voz (STT) podría tardar o fallar.
)

echo.
echo [3/3] Iniciando J.A.R.V.I.S...
echo ============================================================
echo.

cd /d "%~dp0"
python main.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Jarvis finalizó con error. Revisa la consola.
    pause
)
