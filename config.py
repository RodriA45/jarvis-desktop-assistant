"""
Configuración central de Jarvis v5 — editá este archivo con tus API keys y preferencias.
"""
import os
from pathlib import Path

# ── Rutas ──────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
MEMORY_DIR = BASE_DIR / "memory"
UI_DIR     = BASE_DIR / "ui"

# Cargar config_user.json si existe para persistencia
import json
USER_CONFIG_FILE = BASE_DIR / "memory" / "config_user.json"
user_settings = {}
if USER_CONFIG_FILE.exists():
    try:
        user_settings = json.loads(USER_CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass

# ── API Keys ───────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY  = user_settings.get("api_key", os.getenv("ANTHROPIC_API_KEY", "TU_API_KEY_AQUI"))
GEMINI_API_KEY     = user_settings.get("gemini_api_key", os.getenv("GEMINI_API_KEY", ""))
PICOVOICE_API_KEY  = user_settings.get("picovoice_api_key", os.getenv("PICOVOICE_API_KEY", "TU_PICOVOICE_KEY_AQUI"))
ELEVENLABS_API_KEY  = user_settings.get("elevenlabs_api_key", os.getenv("ELEVENLABS_API_KEY", ""))
ELEVENLABS_VOICE_ID = "pNInz6obpgDQGcFmaJgB"

# ── Modelo ─────────────────────────────────────────────────────────────────
LLM_PROVIDER      = user_settings.get("llm_provider", "offline")  # "offline" | "anthropic" | "ollama" | "gemini"
CLAUDE_MODEL      = "claude-sonnet-4-20250514"
CLAUDE_MAX_TOKENS = 1024
OLLAMA_MODEL      = user_settings.get("ollama_model", "llama3")
OLLAMA_HOST       = user_settings.get("ollama_host", "http://localhost:11434")
GEMINI_MODEL      = user_settings.get("gemini_model", "gemini-1.5-flash")

# ── Voz TTS ────────────────────────────────────────────────────────────────
TTS_ENGINE    = user_settings.get("tts_engine", "edge-tts")   # "pyttsx3" | "elevenlabs" | "edge-tts"
TTS_RATE      = int(user_settings.get("tts_rate", 175))
TTS_VOLUME    = float(user_settings.get("tts_volume", 0.95))
TTS_VOICE_LANG = "es"
TTS_VOICE_ID  = user_settings.get("tts_voice_id", "es-AR-TomasNeural")

# ── STT (Whisper) ──────────────────────────────────────────────────────────
WHISPER_MODEL    = user_settings.get("whisper_model", "base")   # tiny | base | small | medium | large
WHISPER_LANGUAGE = "es"
STT_TIMEOUT      = 8
STT_PHRASE_LIMIT = 15

# ── Wake Word ──────────────────────────────────────────────────────────────
WAKE_WORD_MODEL   = str(BASE_DIR / "wake_word" / "jarvis_windows.ppn")
WAKE_WORD_FALLBACK = True

# ── Ventana HUD ────────────────────────────────────────────────────────────
HUD_WIDTH       = int(user_settings.get("hud_width", 1280))
HUD_HEIGHT      = int(user_settings.get("hud_height", 720))
HUD_FRAMELESS   = user_settings.get("hud_frameless", False)
HUD_FULLSCREEN  = user_settings.get("hud_fullscreen", False)
HUD_THEME       = user_settings.get("hud_theme", "cyan")
HUD_ALWAYS_ON_TOP = False

# ── Memoria ────────────────────────────────────────────────────────────────
MEMORY_MAX_TURNS = 20
MEMORY_FILE      = MEMORY_DIR / "context.json"

# ── Personalidad base ──────────────────────────────────────────────────────
JARVIS_PERSONA = """Eres J.A.R.V.I.S (Just A Rather Very Intelligent System), el asistente de IA personal.

Comportamiento:
- Respondé siempre en español rioplatense (Argentina), de forma concisa y directa.
- Usá un tono profesional pero cercano, como el Jarvis de Iron Man.
- Para tareas de sistema, ejecutá la herramienta sin preguntar confirmación salvo que sea destructivo.
- Máximo 2-3 oraciones en respuestas de voz (serán leídas en voz alta).
- Para respuestas largas (código, listas), indicá que mostrás la información en pantalla.
- Tenés memoria semántica: podés recordar conversaciones pasadas.
- Podés ver la pantalla si el usuario te lo pide.
- Podés crear recordatorios y alarmas.

Frases características:
- "Entendido, señor."
- "Por supuesto."
- "De inmediato."
- "Análisis completo."
- "A su disposición."
"""
