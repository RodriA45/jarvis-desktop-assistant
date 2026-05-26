"""
Speaker — Text-to-Speech (pyttsx3 offline o ElevenLabs online)
"""
import asyncio
import io
import os
import re
import threading

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
    def __init__(self):
        self._engine = None
        self._lock = threading.Lock()
        self._mode = TTS_ENGINE
        if self._mode == "pyttsx3":
            self._init_pyttsx3()
        print(f"[SPEAKER] Motor TTS: {self._mode}")

    def _init_pyttsx3(self):
        try:
            import pyttsx3
            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", TTS_RATE)
            self._engine.setProperty("volume", TTS_VOLUME)

            voices = self._engine.getProperty("voices")
            for voice in voices:
                if TTS_VOICE_LANG.lower() in voice.id.lower() or \
                   "spanish" in voice.name.lower() or \
                   "español" in voice.name.lower():
                    self._engine.setProperty("voice", voice.id)
                    print(f"[SPEAKER] Voz seleccionada: {voice.name}")
                    break
        except Exception as e:
            print(f"[SPEAKER] pyttsx3 no disponible: {e}. Usando print.")
            self._mode = "print"

    async def speak(self, text: str):
        clean = _clean_text(text)
        if not clean:
            return
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._speak_sync, clean)

    def _speak_sync(self, text: str):
        if self._mode == "pyttsx3" and self._engine:
            with self._lock:
                try:
                    self._engine.say(text)
                    self._engine.runAndWait()
                except Exception as e:
                    print(f"[SPEAKER] Error TTS: {e}")
                    print(f"[JARVIS VOZ] {text}")
        elif self._mode == "elevenlabs":
            self._speak_elevenlabs(text)
        else:
            print(f"[JARVIS VOZ] {text}")

    def _speak_elevenlabs(self, text: str):
        try:
            import requests
            import sounddevice as sd
            import soundfile as sf

            url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
            headers = {
                "xi-api-key": ELEVENLABS_API_KEY,
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
                print(f"[SPEAKER] ElevenLabs error {r.status_code}")
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
