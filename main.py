"""
J.A.R.V.I.S — Just A Rather Very Intelligent System
Punto de entrada principal — versión mejorada
"""
import asyncio
import sys
import os
import time

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


async def main():
    print("=" * 55)
    print("  J.A.R.V.I.S — Iniciando...")
    print("=" * 55)

    # HUD
    hud = JarvisHUD()
    hud.launch()

    # Módulos
    speaker = Speaker()
    listener = Listener(hud=hud)
    brain = Brain(hud=hud, speaker=speaker)

    # Monitor de sistema en background
    sysmon = SysMonitor(
        hud=hud,
        on_alert=lambda msg: asyncio.run_coroutine_threadsafe(
            speaker.speak(msg), asyncio.get_event_loop()
        )
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


if __name__ == "__main__":
    asyncio.run(main())
