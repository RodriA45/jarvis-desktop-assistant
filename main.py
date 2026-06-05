"""
J.A.R.V.I.S — Just A Rather Very Intelligent System
Punto de entrada principal — versión mejorada
"""
import asyncio
import sys
import os
import time
import signal
import atexit

sys.path.insert(0, os.path.dirname(__file__))

from modules.listener import Listener
from modules.speaker import Speaker
from modules.brain import Brain
from modules.sysmon import SysMonitor
from ui.hud import JarvisHUD


async def boot_sequence(hud: JarvisHUD, speaker: Speaker):
    """Secuencia de arranque cinematográfica."""
    steps = [
        ("ok",     "Inicializando núcleo J.A.R.V.I.S..."),
        ("ok",     "Cargando protocolo de voz..."),
        ("ok",     "Conectando con Claude API..."),
        ("ok",     "Activando memoria semántica..."),
        ("ok",     "Monitor de sistema en línea..."),
        ("ok",     "Sistema de recordatorios activo..."),
        ("ok",     "Módulo de visión listo..."),
        ("active", "Todos los sistemas nominales."),
    ]
    for level, msg in steps:
        hud.add_log(level, msg)
        await asyncio.sleep(0.35)

    hud.update_status("J.A.R.V.I.S en línea. A su disposición, señor.")
    await speaker.speak("J.A.R.V.I.S en línea. A su disposición, señor.")


async def async_main(hud: JarvisHUD):
    # Esperar a que la UI esté lista
    hud._ready.wait(timeout=6)
    await asyncio.sleep(0.3)

    # Módulos
    speaker = Speaker(hud=hud)
    listener = Listener(hud=hud)
    brain = Brain(hud=hud, speaker=speaker)

    # Conectar el clic del micrófono en la interfaz HUD con el disparador
    hud.on_mic_click = lambda: listener.trigger_mic()
    hud.on_stop_speaking = lambda: speaker.stop()
    hud.on_toggle_mute_mic = lambda: listener.toggle_mute()

    # Registrar atajo de teclado global Ctrl + Alt + J
    try:
        import keyboard
        keyboard.add_hotkey('ctrl+alt+j', lambda: listener.trigger_mic())
        print("[JARVIS] Atajo global 'Ctrl+Alt+J' registrado con éxito.")
    except Exception as e:
        print(f"[JARVIS] No se pudo registrar el atajo global: {e}")

    # Monitor de sistema en background
    sysmon = SysMonitor(
        hud=hud,
        on_alert=lambda msg: speaker.speak_now(msg)
    )
    sysmon.start()

    # Secuencia de boot
    await boot_sequence(hud, speaker)

    hud.add_log("active", "Esperando wake word...")
    print("[JARVIS] Sistema en línea. Di 'Jarvis' para activar.")

    while True:
        try:
            await listener.wait_for_wake_word()

            hud.set_listening(True)
            hud.add_log("active", "Wake word — escuchando...")
            speaker.play_tone("activate")

            text = await listener.listen()
            hud.set_listening(False)

            if not text or len(text.strip()) < 2:
                hud.add_log("warn", "No se entendió el comando")
                hud.update_status("No entendí. ¿Podés repetir?")
                await speaker.speak("No entendí. ¿Podés repetir?")
                continue

            print(f"\n[TÚ] {text}")
            hud.add_log("active", f"Cmd: {text[:55]}")
            hud.update_status("Procesando...")

            response = await brain.process(text)

            print(f"[JARVIS] {response}")
            hud.update_status(response)
            hud.add_log("ok", "Respuesta generada")

            await speaker.speak(response)

        except KeyboardInterrupt:
            print("\n[JARVIS] Apagando sistema...")
            hud.add_log("warn", "Sistema apagado por el usuario")
            sysmon.stop()
            break
        except Exception as e:
            print(f"[ERROR] {e}")
            hud.add_log("warn", f"Error: {str(e)[:45]}")
            await asyncio.sleep(1)


def start_jarvis_backend(hud: JarvisHUD):
    import threading
    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(async_main(hud))
        
    t = threading.Thread(target=_run, daemon=True)
    t.start()


def cleanup_and_exit(signum=None, frame=None):
    print("\n[JARVIS] Apagando J.A.R.V.I.S y cerrando procesos en segundo plano...")
    import os
    try:
        os.system("taskkill /f /im ollama.exe >nul 2>&1")
    except Exception:
        pass
    os._exit(0)

# Registrar manejadores de señales para un apagado limpio
signal.signal(signal.SIGINT, cleanup_and_exit)
signal.signal(signal.SIGTERM, cleanup_and_exit)
if hasattr(signal, "SIGBREAK"):
    signal.signal(signal.SIGBREAK, cleanup_and_exit)
atexit.register(cleanup_and_exit)


def main():
    print("=" * 55)
    print("  J.A.R.V.I.S — Iniciando...")
    print("=" * 55)

    # HUD
    hud = JarvisHUD()
    
    # Iniciar backend en un hilo separado
    start_jarvis_backend(hud)
    
    # Lanzar la UI en el hilo principal (esto bloquea el proceso)
    hud.launch()


if __name__ == "__main__":
    main()
