"""
JarvisHUD — HUD mejorado con panel de config, métricas reales y soporte para recordatorios.
"""
import os
import json
import threading
import time

try:
    import webview
    WEBVIEW_OK = True
except ImportError:
    WEBVIEW_OK = False

HUD_HTML = os.path.join(os.path.dirname(__file__), "hud.html")


class HudAPI:
    """Métodos accesibles desde JS via window.pywebview.api.*"""
    def __init__(self, bridge):
        self._bridge = bridge

    def mic_clicked(self):
        if self._bridge.on_mic_click:
            self._bridge.on_mic_click()

    def ready(self):
        self._bridge._ready.set()

    def shutdown(self):
        """Mata todos los procesos y apaga Jarvis."""
        self._bridge.shutdown()

    def save_settings(self, settings_json: str):
        """Guarda ajustes desde el panel de config."""
        try:
            settings = json.loads(settings_json)
            self._bridge._apply_settings(settings)
            return "ok"
        except Exception as e:
            return f"error: {e}"

    def get_settings(self) -> str:
        """Devuelve los ajustes actuales."""
        return json.dumps(self._bridge._current_settings())

    def toggle_mute_mic(self) -> bool:
        return self._bridge.toggle_mute_mic()

    def stop_speaking(self):
        self._bridge.stop_speaking()


class JarvisHUD:
    def __init__(self):
        self._window = None
        self._ready = threading.Event()
        self.on_mic_click = None
        self.on_toggle_mute_mic = None
        self.on_stop_speaking = None
        self._settings_callbacks = []

    def toggle_mute_mic(self) -> bool:
        if self.on_toggle_mute_mic:
            return self.on_toggle_mute_mic()
        return False

    def stop_speaking(self):
        if self.on_stop_speaking:
            self.on_stop_speaking()

    def launch(self):
        if not WEBVIEW_OK:
            print("[HUD] pywebview no instalado — HUD desactivado.")
            return
        if not os.path.exists(HUD_HTML):
            print(f"[HUD] Archivo no encontrado: {HUD_HTML}")
            return

        api = HudAPI(self)

        from config import HUD_WIDTH, HUD_HEIGHT, HUD_FRAMELESS, HUD_ALWAYS_ON_TOP, HUD_FULLSCREEN
        self._window = webview.create_window(
            title="J.A.R.V.I.S",
            url=f"file:///{HUD_HTML.replace(os.sep, '/')}",
            width=HUD_WIDTH, height=HUD_HEIGHT,
            resizable=True, frameless=HUD_FRAMELESS,
            on_top=HUD_ALWAYS_ON_TOP,
            background_color="#000000",
            js_api=api, min_size=(800, 500),
            fullscreen=HUD_FULLSCREEN
        )
        
        def _on_closed():
            print("[HUD] Ventana cerrada. Apagando J.A.R.V.I.S...")
            self.shutdown()
            
        self._window.events.closed += _on_closed

        def _on_shown():
            # Intentar cambiar el icono nativo de la ventana en Windows
            try:
                import platform
                if platform.system() == "Windows" and self._window and hasattr(self._window, "native"):
                    import clr
                    clr.AddReference('System.Windows.Forms')
                    clr.AddReference('System.Drawing')
                    import System.Drawing
                    icon_path = os.path.join(os.path.dirname(HUD_HTML), "jarvis.ico")
                    if os.path.exists(icon_path):
                        native_window = self._window.native
                        try:
                            # Intentar método para WinForms (System.Drawing.Icon)
                            native_window.Icon = System.Drawing.Icon(icon_path)
                            print("[HUD] Icono de Jarvis asignado correctamente (WinForms).")
                        except Exception:
                            # Intentar método para WPF (BitmapFrame)
                            try:
                                clr.AddReference('PresentationCore')
                                clr.AddReference('WindowsBase')
                                from System.Windows.Media.Imaging import BitmapFrame
                                from System import Uri
                                native_window.Icon = BitmapFrame.Create(Uri(icon_path))
                                print("[HUD] Icono de Jarvis asignado correctamente (WPF).")
                            except Exception as e2:
                                print(f"[HUD] No se pudo cambiar el icono en WPF: {e2}")
            except Exception:
                pass

        webview.start(_on_shown, debug=False)

    def _js(self, code: str):
        if self._window:
            try:
                self._window.evaluate_js(code)
            except Exception:
                pass

    def _esc(self, text: str) -> str:
        return (str(text)
                .replace("\\", "\\\\")
                .replace("'", "\\'")
                .replace("\n", " ")
                .replace("\r", ""))

    # ── Métodos públicos ────────────────────────────────────────────────────

    def update_status(self, text: str):
        self._js(f"window.jarvis && jarvis.setResponse('{self._esc(text)}')")

    def set_listening(self, active: bool):
        self._js(f"window.jarvis && jarvis.setListening({'true' if active else 'false'})")

    def add_log(self, level: str, msg: str):
        self._js(f"window.jarvis && jarvis.addLog('{level}', '{self._esc(msg)}')")

    def update_metrics(self, cpu: int, ram: int, tokens: int, latency: int):
        self._js(f"window.jarvis && jarvis.updateMetrics({cpu},{ram},{tokens},{latency})")

    def update_metrics_full(self, cpu: int, ram: int, disk: int,
                             tx: float, rx: float, temp=None,
                             gpu_load=None, gpu_temp=None):
        """Llamado por SysMonitor con datos reales."""
        temp_val = round(temp, 1) if temp is not None else "null"
        gpu_load_val = int(gpu_load) if gpu_load is not None else "null"
        gpu_temp_val = int(gpu_temp) if gpu_temp is not None else "null"
        self._js(
            f"window.jarvis && jarvis.updateMetricsFull("
            f"{cpu},{ram},{disk},{tx},{rx},{temp_val},{gpu_load_val},{gpu_temp_val})"
        )

    def show_reminder(self, text: str):
        self._js(f"window.jarvis && jarvis.showReminder('{self._esc(text)}')")

    def update_reminders(self, reminders: list):
        data = json.dumps(reminders)
        safe = data.replace("'", "\\'")
        self._js(f"window.jarvis && jarvis.updateReminders('{safe}')")

    # ── Settings & Control ───────────────────────────────────────────────────

    def shutdown(self):
        """Matar procesos asociados y terminar el programa."""
        print("[HUD] Apagando J.A.R.V.I.S y cerrando procesos en segundo plano...")
        import os
        try:
            os.system("taskkill /f /im ollama.exe >nul 2>&1")
        except Exception:
            pass
        os._exit(0)

    def _current_settings(self) -> dict:
        try:
            from config import (ANTHROPIC_API_KEY, GEMINI_API_KEY, TTS_ENGINE, TTS_RATE, TTS_VOLUME,
                                WHISPER_MODEL, LLM_PROVIDER, OLLAMA_MODEL, ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, TTS_VOICE_ID,
                                HUD_WIDTH, HUD_HEIGHT, HUD_FRAMELESS, HUD_FULLSCREEN, HUD_THEME)
            
            # Obtener voces locales disponibles
            voices = []
            try:
                import pyttsx3
                engine = pyttsx3.init()
                for v in engine.getProperty("voices"):
                    voices.append({"id": v.id, "name": v.name})
            except Exception:
                pass

            return {
                "tts_engine": TTS_ENGINE,
                "tts_rate": TTS_RATE,
                "tts_volume": TTS_VOLUME,
                "tts_voice_id": TTS_VOICE_ID,
                "whisper_model": WHISPER_MODEL,
                "api_key": ANTHROPIC_API_KEY if ANTHROPIC_API_KEY != "TU_API_KEY_AQUI" else "",
                "gemini_api_key": GEMINI_API_KEY,
                "llm_provider": LLM_PROVIDER,
                "ollama_model": OLLAMA_MODEL,
                "elevenlabs_api_key": ELEVENLABS_API_KEY,
                "elevenlabs_voice_id": ELEVENLABS_VOICE_ID,
                "hud_width": HUD_WIDTH,
                "hud_height": HUD_HEIGHT,
                "hud_frameless": HUD_FRAMELESS,
                "hud_fullscreen": HUD_FULLSCREEN,
                "hud_theme": HUD_THEME,
                "available_voices": voices
            }
        except Exception:
            return {}

    def _apply_settings(self, settings: dict):
        """Aplica ajustes en caliente (sin reiniciar) y los persiste en disco."""
        import config
        if "tts_rate" in settings:
            config.TTS_RATE = int(settings["tts_rate"])
        if "tts_volume" in settings:
            config.TTS_VOLUME = float(settings["tts_volume"])
        if "tts_engine" in settings:
            config.TTS_ENGINE = settings["tts_engine"]
        if "tts_voice_id" in settings:
            config.TTS_VOICE_ID = settings["tts_voice_id"]
        if "whisper_model" in settings:
            config.WHISPER_MODEL = settings["whisper_model"]
        if "api_key" in settings:
            config.ANTHROPIC_API_KEY = settings["api_key"]
        if "gemini_api_key" in settings:
            config.GEMINI_API_KEY = settings["gemini_api_key"]
        if "llm_provider" in settings:
            config.LLM_PROVIDER = settings["llm_provider"]
        if "ollama_model" in settings:
            config.OLLAMA_MODEL = settings["ollama_model"]
        if "elevenlabs_api_key" in settings:
            config.ELEVENLABS_API_KEY = settings["elevenlabs_api_key"]
        if "elevenlabs_voice_id" in settings:
            config.ELEVENLABS_VOICE_ID = settings["elevenlabs_voice_id"]
        if "hud_width" in settings:
            config.HUD_WIDTH = int(settings["hud_width"])
        if "hud_height" in settings:
            config.HUD_HEIGHT = int(settings["hud_height"])
        if "hud_frameless" in settings:
            config.HUD_FRAMELESS = bool(settings["hud_frameless"])
        if "hud_fullscreen" in settings:
            config.HUD_FULLSCREEN = bool(settings["hud_fullscreen"])
        if "hud_theme" in settings:
            config.HUD_THEME = settings["hud_theme"]
            self._js(f"window.jarvis && jarvis.setTheme('{config.HUD_THEME}')")

        # Aplicar modo pantalla completa en caliente
        if "hud_fullscreen" in settings and self._window:
            is_fs = bool(settings["hud_fullscreen"])
            try:
                current_fs = False
                try:
                    current_fs = self._window.attributes("-fullscreen")
                except Exception:
                    pass
                if current_fs != is_fs:
                    try:
                        self._window.attributes("-fullscreen", is_fs)
                    except Exception:
                        self._window.toggle_fullscreen()
                    print(f"[HUD] Pantalla completa cambiada en caliente a: {is_fs}")
            except Exception as e:
                print(f"[HUD] Error cambiando a pantalla completa: {e}")

        # Redimensionar la ventana en caliente si cambió el tamaño (y no está en pantalla completa)
        if ("hud_width" in settings or "hud_height" in settings) and self._window and not config.HUD_FULLSCREEN:
            try:
                self._window.resize(config.HUD_WIDTH, config.HUD_HEIGHT)
                print(f"[HUD] Ventana redimensionada a: {config.HUD_WIDTH}x{config.HUD_HEIGHT}")
            except Exception as e:
                print(f"[HUD] Error redimensionando ventana: {e}")

        # Persistir en config_user.json
        try:
            user_config_path = config.MEMORY_DIR / "config_user.json"
            existing = {}
            if user_config_path.exists():
                try:
                    existing = json.loads(user_config_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            existing.update(settings)
            user_config_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"[HUD] Ajustes persistidos en: {user_config_path}")
        except Exception as e:
            print(f"[HUD] Error persistiendo ajustes: {e}")

        print(f"[HUD] Settings aplicados: {settings}")
        for cb in self._settings_callbacks:
            cb(settings)

    def on_settings_change(self, callback):
        self._settings_callbacks.append(callback)
