"""
Speaker — Text-to-Speech (pyttsx3 offline o ElevenLabs online)
"""
import asyncio
import io
import os
import re
import threading
import queue

from config import (TTS_ENGINE, TTS_RATE, TTS_VOLUME, TTS_VOICE_LANG,
                    ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID)


def _clean_text(text: str) -> str:
    """Limpia el texto antes de sintetizarlo: quita markdown, URLs, etc."""
    text = re.sub(r"```.*?```", "código omitido", text, flags=re.DOTALL)
    text = re.sub(r"`[^`]+`", "", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"https?://\S+", "el enlace", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > 400:
        text = text[:397] + "..."
    return text


class Speaker:
    def __init__(self, hud=None):
        self.hud = hud
        self._queue = queue.Queue()
        self._engine = None
        self._lock = threading.Lock()
        self._mode = TTS_ENGINE
        
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
        print(f"[SPEAKER] Motor TTS: {self._mode} (Hilo dedicado iniciado)")

    def _worker(self):
        # Inicializar pyttsx3 en este hilo dedicado para evitar problemas de COM
        if self._mode == "pyttsx3":
            self._init_pyttsx3()
            
        while True:
            try:
                text = self._queue.get()
                if text is None:
                    break
                self._speak_sync(text)
                self._queue.task_done()
            except Exception as e:
                print(f"[SPEAKER WORKER] Error: {e}")

    def _init_pyttsx3(self):
        try:
            import pyttsx3
            import config
            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", config.TTS_RATE)
            self._engine.setProperty("volume", config.TTS_VOLUME)

            voices = self._engine.getProperty("voices")
            if hasattr(config, "TTS_VOICE_ID") and config.TTS_VOICE_ID:
                try:
                    self._engine.setProperty("voice", config.TTS_VOICE_ID)
                    voice_name = next((v.name for v in voices if v.id == config.TTS_VOICE_ID), config.TTS_VOICE_ID)
                    print(f"[SPEAKER] Voz cargada: {voice_name}")
                except Exception:
                    pass
            else:
                for voice in voices:
                    if config.TTS_VOICE_LANG.lower() in voice.id.lower() or \
                       "spanish" in voice.name.lower() or \
                       "español" in voice.name.lower():
                        self._engine.setProperty("voice", voice.id)
                        print(f"[SPEAKER] Voz seleccionada por defecto: {voice.name}")
                        break
        except Exception as e:
            print(f"[SPEAKER] pyttsx3 no disponible: {e}. Usando print.")
            self._mode = "print"

    def speak_now(self, text: str):
        clean = _clean_text(text)
        if not clean:
            return
        self._queue.put(clean)

    async def speak(self, text: str):
        self.speak_now(text)

    def _speak_sync(self, text: str):
        import config
        self._mode = config.TTS_ENGINE
        
        if self.hud:
            self.hud._js("window.jarvis && jarvis.setSpeaking(true)")
            
        try:
            if self._mode == "pyttsx3":
                if not self._engine:
                    self._init_pyttsx3()
                with self._lock:
                    try:
                        self._engine.setProperty("rate", config.TTS_RATE)
                        self._engine.setProperty("volume", config.TTS_VOLUME)
                        if hasattr(config, "TTS_VOICE_ID") and config.TTS_VOICE_ID:
                            self._engine.setProperty("voice", config.TTS_VOICE_ID)
                        self._engine.say(text)
                        self._engine.runAndWait()
                    except Exception as e:
                        print(f"[SPEAKER] Error TTS: {e}")
                        print(f"[JARVIS VOZ] {text}")
            elif self._mode == "elevenlabs":
                self._speak_elevenlabs(text)
            else:
                print(f"[JARVIS VOZ] {text}")
        finally:
            if self.hud:
                self.hud._js("window.jarvis && jarvis.setSpeaking(false)")

    def _speak_elevenlabs(self, text: str):
        try:
            import requests
            import sounddevice as sd
            import soundfile as sf
            import config

            url = f"https://api.elevenlabs.io/v1/text-to-speech/{config.ELEVENLABS_VOICE_ID}"
            headers = {
                "xi-api-key": config.ELEVENLABS_API_KEY,
                "Content-Type": "application/json"
            }
            payload = {
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.8}
            }
            r = requests.post(url, headers=headers, json=payload, timeout=15)
            if r.status_code == 200:
                buf = io.BytesIO(r.content)
                data, samplerate = sf.read(buf)
                sd.play(data, samplerate)
                sd.wait()
            else:
                print(f"[SPEAKER] ElevenLabs error {r.status_code}: {r.text}")
        except Exception as e:
            print(f"[SPEAKER] ElevenLabs falló: {e}")

    def play_tone(self, tone_type: str = "activate"):
        """Reproduce un beep corto de activación."""
        try:
            import sounddevice as sd
            import numpy as np
            sr = 22050
            if tone_type == "activate":
                freq, dur = 880, 0.12
            else:
                freq, dur = 440, 0.1
            t = np.linspace(0, dur, int(sr * dur), False)
            wave = np.sin(2 * np.pi * freq * t) * 0.3
            envelope = np.ones_like(wave)
            fade = int(sr * 0.02)
            envelope[:fade] = np.linspace(0, 1, fade)
            envelope[-fade:] = np.linspace(1, 0, fade)
            sd.play((wave * envelope).astype(np.float32), sr)
            sd.wait()
        except Exception:
            pass
