"""
Listener — Wake word (Picovoice Porcupine) + STT (Whisper)
"""
import asyncio
import os
import struct
import wave
import tempfile
import threading
import numpy as np

try:
    import pvporcupine
    PORCUPINE_AVAILABLE = True
except ImportError:
    PORCUPINE_AVAILABLE = False

try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False

try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    SR_AVAILABLE = False

from config import (PICOVOICE_API_KEY, WAKE_WORD_MODEL, WAKE_WORD_FALLBACK,
                    WHISPER_MODEL, WHISPER_LANGUAGE, STT_TIMEOUT, STT_PHRASE_LIMIT)


class Listener:
    def __init__(self, hud=None):
        self.hud = hud
        self.muted = False
        self._whisper_model = None
        self._porcupine = None
        self._use_whisper = WHISPER_AVAILABLE and SOUNDDEVICE_AVAILABLE
        self._wake_mode = self._detect_wake_mode()
        self.loop = asyncio.get_event_loop()
        self.mic_trigger_event = asyncio.Event()

        print(f"[LISTENER] Wake mode: {self._wake_mode}")
        print(f"[LISTENER] STT: {'Whisper' if self._use_whisper else 'SpeechRecognition'}")

        # Iniciar carga de Whisper de fondo para evitar bloqueos
        if self._use_whisper:
            threading.Thread(target=self._load_whisper, daemon=True).start()

    def trigger_mic(self):
        """Dispara el micrófono de forma segura desde otro hilo (como la GUI)."""
        print("[LISTENER] Disparador de micrófono desde HUD activado.")
        self.loop.call_soon_threadsafe(self.mic_trigger_event.set)

    def toggle_mute(self) -> bool:
        self.muted = not self.muted
        print(f"[LISTENER] Micrófono silenciado: {self.muted}")
        return self.muted

    def _detect_wake_mode(self):
        if (PORCUPINE_AVAILABLE
                and SOUNDDEVICE_AVAILABLE
                and os.path.exists(WAKE_WORD_MODEL)
                and PICOVOICE_API_KEY != "TU_PICOVOICE_KEY_AQUI"):
            return "porcupine"
        if WAKE_WORD_FALLBACK:
            return "keyboard"
        return "keyboard"

    def _load_whisper(self):
        if self._whisper_model is None and self._use_whisper:
            print(f"[LISTENER] Cargando Whisper ({WHISPER_MODEL}) de fondo...")
            try:
                import whisper
                self._whisper_model = whisper.load_model(WHISPER_MODEL)
                print("[LISTENER] Whisper listo.")
            except Exception as e:
                print(f"[LISTENER] Error cargando Whisper: {e}")

    async def wait_for_wake_word(self):
        self.mic_trigger_event.clear()
        
        # Si el micrófono está silenciado, esperar a que se desactive el silencio
        while self.muted:
            await asyncio.sleep(0.5)
        
        async def detect_wake():
            if self._wake_mode == "porcupine":
                try:
                    await self._wait_porcupine()
                except Exception as e:
                    print(f"[LISTENER] Error en Picovoice: {e}. Degradando a modo teclado.")
                    if self.hud:
                        self.hud.add_log("warn", "Picovoice falló. Fallback teclado.")
                    self._wake_mode = "keyboard"
                    await self._wait_keyboard()
            else:
                await self._wait_keyboard()

        wake_task = asyncio.create_task(detect_wake())
        mic_task = asyncio.create_task(self.mic_trigger_event.wait())

        done, pending = await asyncio.wait(
            [wake_task, mic_task],
            return_when=asyncio.FIRST_COMPLETED
        )

        for t in pending:
            t.cancel()
            try:
                await asyncio.wait_for(t, timeout=0.1)
            except BaseException:
                pass

    async def _wait_keyboard(self):
        if self.hud:
            print("[LISTENER] Esperando click de micrófono en el HUD...")
            self.hud.update_status("Esperando activación de micrófono...")
            while True:
                await asyncio.sleep(3600)
        else:
            loop = asyncio.get_event_loop()
            print("[LISTENER] Presioná ENTER para hablar...")
            await loop.run_in_executor(None, input)

    async def _wait_porcupine(self):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._porcupine_blocking)

    def _porcupine_blocking(self):
        import pvporcupine
        import sounddevice as sd

        porcupine = pvporcupine.create(
            access_key=PICOVOICE_API_KEY,
            keyword_paths=[WAKE_WORD_MODEL]
        )
        try:
            with sd.RawInputStream(
                samplerate=porcupine.sample_rate,
                blocksize=porcupine.frame_length,
                dtype="int16",
                channels=1
            ) as stream:
                while True:
                    pcm, _ = stream.read(porcupine.frame_length)
                    pcm = struct.unpack_from("h" * porcupine.frame_length, pcm)
                    result = porcupine.process(pcm)
                    if result >= 0:
                        return
        finally:
            porcupine.delete()

    async def listen(self) -> str:
        loop = asyncio.get_event_loop()
        if self._use_whisper:
            def _wait_and_listen():
                import time
                start_t = time.time()
                # Esperar a que se complete la carga de fondo (máx 30s)
                while self._whisper_model is None and time.time() - start_t < 30:
                    time.sleep(0.2)
                if self._whisper_model is None:
                    self._load_whisper()
                
                if self._whisper_model is None:
                    print("[LISTENER] Whisper no pudo cargarse. Usando SpeechRecognition como fallback.")
                    if self.hud:
                        self.hud.add_log("warn", "Whisper no disponible. Usando SR.")
                    return self._listen_sr()
                return self._listen_whisper()
            return await loop.run_in_executor(None, _wait_and_listen)
        elif SR_AVAILABLE:
            return await loop.run_in_executor(None, self._listen_sr)
        else:
            return await loop.run_in_executor(None, lambda: input("Tu mensaje: "))

    def _listen_whisper(self) -> str:
        import sounddevice as sd
        import numpy as np
        samplerate = 16000
        print("[STT] Grabando con VAD activo...")

        # Configuraciones de VAD
        chunk_size = 1024  # ~64ms chunks
        silence_threshold = 0.008  # Umbral RMS para detectar silencio
        max_silence_chunks = int(1.5 * samplerate / chunk_size)  # 1.5s de silencio
        min_recording_chunks = int(1.0 * samplerate / chunk_size) # Al menos 1s de audio
        max_wait_chunks = int(5.0 * samplerate / chunk_size)  # Esperar máx 5s si no empieza a hablar
        max_chunks = int(STT_PHRASE_LIMIT * samplerate / chunk_size)

        chunks = []
        voice_started = False
        silence_chunks = 0

        try:
            with sd.InputStream(
                samplerate=samplerate,
                channels=1,
                dtype="float32"
            ) as stream:
                for _ in range(max_chunks):
                    chunk, _ = stream.read(chunk_size)
                    chunks.append(chunk)

                    # Calcular RMS (Root Mean Square) del chunk
                    rms = np.sqrt(np.mean(chunk**2))
                    if rms > silence_threshold:
                        if not voice_started:
                            print("[STT] Voz detectada...")
                            voice_started = True
                        silence_chunks = 0
                    else:
                        if voice_started:
                            silence_chunks += 1
                            if len(chunks) >= min_recording_chunks and silence_chunks > max_silence_chunks:
                                print("[STT] Fin de habla detectado.")
                                break
                        elif len(chunks) > max_wait_chunks:
                            print("[STT] Tiempo de espera agotado sin voz.")
                            break
        except Exception as e:
            print(f"[STT] Error en grabación: {e}")
            return ""

        if not chunks or (not voice_started and len(chunks) >= max_wait_chunks):
            return ""

        audio = np.concatenate(chunks).flatten()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_path = f.name

        with wave.open(tmp_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(samplerate)
            wf.writeframes((audio * 32767).astype(np.int16).tobytes())

        try:
            if self._whisper_model is None:
                raise ValueError("Modelo Whisper no inicializado.")
            result = self._whisper_model.transcribe(
                tmp_path,
                language=WHISPER_LANGUAGE,
                fp16=False
            )
            text = result["text"].strip()
            print(f"[STT] Transcripción: {text}")
            return text
        except Exception as e:
            print(f"[STT] Error Whisper: {e}. Fallback a SpeechRecognition.")
            if self.hud:
                self.hud.add_log("warn", "Error STT Whisper, intentando SR...")
            return self._listen_sr()
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

    def _listen_sr(self) -> str:
        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            print("[STT] Escuchando...")
            try:
                audio = recognizer.listen(
                    source,
                    timeout=STT_TIMEOUT,
                    phrase_time_limit=STT_PHRASE_LIMIT
                )
                text = recognizer.recognize_google(audio, language=f"{WHISPER_LANGUAGE}-AR")
                print(f"[STT] Reconocido: {text}")
                return text
            except sr.WaitTimeoutError:
                return ""
            except sr.UnknownValueError:
                return ""
            except Exception as e:
                print(f"[STT] Error: {e}")
                return ""
