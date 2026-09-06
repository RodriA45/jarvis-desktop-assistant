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
    def __init__(self, hud: object = None) -> None:
        self.hud = hud
        self._queue = queue.Queue()
        self._engine = None
        self._lock = threading.Lock()
        self._mode = TTS_ENGINE
        
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
        print(f"[SPEAKER] Motor TTS: {self._mode} (Hilo dedicado iniciado)")

    def _worker(self) -> None:
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
                import traceback
                print(f"[SPEAKER WORKER] Error: {e}")
                traceback.print_exc()

    def _init_pyttsx3(self) -> None:
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
            import traceback
            print(f"[SPEAKER] pyttsx3 no disponible: {e}. Usando print.")
            traceback.print_exc()
            self._mode = "print"

    def stop(self) -> None:
        """Para la reproducción de voz inmediatamente y vacía la cola."""
        import queue
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except Exception:
                break
        
        if self._mode == "pyttsx3" and self._engine:
            try:
                self._engine.stop()
            except Exception as e:
                import traceback
                print(f"[SPEAKER] Error deteniendo motor pyttsx3: {e}")
                traceback.print_exc()
        elif self._mode == "elevenlabs":
            try:
                import sounddevice as sd
                sd.stop()
            except Exception:
                pass
        elif self._mode == "edge-tts":
            try:
                import pygame
                if pygame.mixer.get_init():
                    pygame.mixer.music.stop()
            except Exception:
                pass

    def speak_now(self, text: str) -> None:
        clean = _clean_text(text)
        if not clean:
            return
        self._queue.put(clean)

    async def speak(self, text: str) -> None:
        self.speak_now(text)

    def _speak_sync(self, text: str) -> None:
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
                        import traceback
                        print(f"[SPEAKER] Error TTS: {e}")
                        traceback.print_exc()
                        print(f"[JARVIS VOZ] {text}")
            elif self._mode == "edge-tts":
                self._speak_edge_tts(text)
            elif self._mode == "elevenlabs":
                self._speak_elevenlabs(text)
            else:
                print(f"[JARVIS VOZ] {text}")
        finally:
            if self.hud:
                self.hud._js("window.jarvis && jarvis.setSpeaking(false)")

    def _speak_edge_tts(self, text: str) -> None:
        try:
            import edge_tts
            import asyncio
            import tempfile
            import os
            import pygame
            import config
            
            voice = getattr(config, "TTS_VOICE_ID", "")
            if not voice:
                voice = "es-AR-TomasNeural"
                
            communicate = edge_tts.Communicate(text, voice)
            
            fd, temp_path = tempfile.mkstemp(suffix=".mp3")
            os.close(fd)
            
            # Ejecutar generación en el event loop nuevo de este thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(communicate.save(temp_path))
            loop.close()
            
            # Reproducir con pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init()
                
            pygame.mixer.music.load(temp_path)
            pygame.mixer.music.set_volume(config.TTS_VOLUME)
            pygame.mixer.music.play()
            
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
                
            pygame.mixer.music.unload()
            # No cerramos pygame.mixer quit() para reuso eficiente
            
            try:
                os.remove(temp_path)
            except Exception:
                pass
                
        except Exception as e:
            import traceback
            print(f"[SPEAKER] Edge TTS falló: {e}")
            traceback.print_exc()

    def _speak_elevenlabs(self, text: str) -> None:
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
            import traceback
            print(f"[SPEAKER] ElevenLabs falló: {e}")
            traceback.print_exc()

    def play_tone(self, tone_type: str = "activate") -> None:
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
