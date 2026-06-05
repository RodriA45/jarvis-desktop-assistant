"""
SystemController — Control de Windows: apps, volumen, teclado, captura, comandos.
"""
import os
import subprocess
import time
import datetime
import json

try:
    import pyautogui
    pyautogui.FAILSAFE = False
    PYAUTOGUI_OK = True
except Exception:
    PYAUTOGUI_OK = False

try:
    import psutil
    PSUTIL_OK = True
except Exception:
    PSUTIL_OK = False

APP_MAP = {
    "chrome":       "chrome.exe",
    "google":       "chrome.exe",
    "firefox":      "firefox.exe",
    "edge":         "msedge.exe",
    "notepad":      "notepad.exe",
    "bloc de notas":"notepad.exe",
    "spotify":      "spotify.exe",
    "vscode":       "code",
    "visual studio code": "code",
    "explorer":     "explorer.exe",
    "archivos":     "explorer.exe",
    "terminal":     "wt.exe",
    "calc":         "calc.exe",
    "calculadora":  "calc.exe",
    "paint":        "mspaint.exe",
    "word":         "winword.exe",
    "excel":        "excel.exe",
    "powerpoint":   "powerpnt.exe",
    "outlook":      "outlook.exe",
    "teams":        "teams.exe",
    "discord":      "discord.exe",
    "steam":        "steam.exe",
    "vlc":          "vlc.exe",
    "zoom":         "zoom.exe",
    "obs":          "obs64.exe",
    "photoshop":    "photoshop.exe",
    "cmd":          "cmd.exe",
    "powershell":   "powershell.exe",
    "taskmgr":      "taskmgr.exe",
    "administrador de tareas": "taskmgr.exe",
}


class SystemController:
    def open_app(self, app_name: str) -> str:
        key = app_name.lower().strip()
        exe = APP_MAP.get(key, app_name)
        try:
            subprocess.Popen(exe, shell=True)
            return f"Abriendo {app_name}."
        except Exception as e:
            return f"No pude abrir '{app_name}': {e}"

    def volume(self, action: str, value: int = 50) -> str:
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            vol = cast(interface, POINTER(IAudioEndpointVolume))

            if action == "mute":
                vol.SetMute(1, None)
                return "Sistema silenciado."
            elif action == "unmute":
                vol.SetMute(0, None)
                return "Silencio desactivado."
            elif action == "up":
                cur = vol.GetMasterVolumeLevelScalar()
                vol.SetMasterVolumeLevelScalar(min(1.0, cur + 0.15), None)
                return f"Volumen subido a {int(min(1.0, cur + 0.15) * 100)}%."
            elif action == "down":
                cur = vol.GetMasterVolumeLevelScalar()
                vol.SetMasterVolumeLevelScalar(max(0.0, cur - 0.15), None)
                return f"Volumen bajado a {int(max(0.0, cur - 0.15) * 100)}%."
            elif action == "set":
                vol.SetMasterVolumeLevelScalar(value / 100.0, None)
                return f"Volumen al {value}%."
        except ImportError:
            # Fallback sin pycaw: usa nircmd o PowerShell
            if action == "mute":
                subprocess.run("powershell -c \"$obj = New-Object -com wscript.shell; $obj.SendKeys([char]173)\"", shell=True)
                return "Silenciado."
            elif action == "up":
                for _ in range(3):
                    subprocess.run("powershell -c \"$obj = New-Object -com wscript.shell; $obj.SendKeys([char]175)\"", shell=True)
                return "Volumen subido."
            elif action == "down":
                for _ in range(3):
                    subprocess.run("powershell -c \"$obj = New-Object -com wscript.shell; $obj.SendKeys([char]174)\"", shell=True)
                return "Volumen bajado."
        except Exception as e:
            return f"Error al controlar volumen: {e}"

    def type_text(self, text: str) -> str:
        if not PYAUTOGUI_OK:
            return "pyautogui no disponible."
        try:
            time.sleep(0.3)
            pyautogui.write(text, interval=0.04)
            return "Texto escrito."
        except Exception as e:
            return f"Error al escribir: {e}"

    def screenshot(self, filename: str = None) -> str:
        if not PYAUTOGUI_OK:
            return "pyautogui no disponible."
        try:
            if not filename:
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"jarvis_screenshot_{ts}"
            path = os.path.join(os.path.expanduser("~"), "Pictures", f"{filename}.png")
            img = pyautogui.screenshot()
            img.save(path)
            return f"Captura guardada en {path}."
        except Exception as e:
            return f"Error al capturar: {e}"

    def open_url(self, url: str) -> str:
        try:
            import webbrowser
            webbrowser.open(url)
            return f"Abriendo {url} en el navegador."
        except Exception as e:
            return f"No pude abrir la URL: {e}"

    def run_command(self, command: str, shell: str = "cmd") -> str:
        BLOCKED = ["format", "del /s", "rd /s", "rm -rf", "shutdown /r", "shutdown /s"]
        for b in BLOCKED:
            if b in command.lower():
                return f"Comando bloqueado por seguridad: contiene '{b}'."
        try:
            if shell == "powershell":
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", command],
                    capture_output=True, text=True, timeout=15
                )
            else:
                result = subprocess.run(
                    command, shell=True, capture_output=True, text=True, timeout=15
                )
            output = (result.stdout + result.stderr).strip()
            if len(output) > 500:
                output = output[:497] + "..."
            return output or "Comando ejecutado sin salida."
        except subprocess.TimeoutExpired:
            return "El comando tardó demasiado y fue cancelado."
        except Exception as e:
            return f"Error: {e}"

    def get_info(self, info_type: str) -> str:
        if not PSUTIL_OK:
            return "psutil no disponible. Instalá con: pip install psutil"
        try:
            data = {}
            if info_type in ("all", "cpu"):
                data["cpu_percent"] = psutil.cpu_percent(interval=0.5)
                data["cpu_cores"] = psutil.cpu_count()
            if info_type in ("all", "ram"):
                mem = psutil.virtual_memory()
                data["ram_total_gb"] = round(mem.total / 1e9, 1)
                data["ram_used_gb"] = round(mem.used / 1e9, 1)
                data["ram_percent"] = mem.percent
            if info_type in ("all", "disk"):
                disk = psutil.disk_usage("/")
                data["disk_total_gb"] = round(disk.total / 1e9, 1)
                data["disk_used_gb"] = round(disk.used / 1e9, 1)
                data["disk_percent"] = disk.percent
            if info_type in ("all", "battery"):
                bat = psutil.sensors_battery()
                if bat:
                    data["battery_percent"] = bat.percent
                    data["charging"] = bat.power_plugged
            if info_type in ("all", "network"):
                data["ip"] = subprocess.run("ipconfig", capture_output=True, text=True).stdout[:200]
            if info_type == "processes":
                procs = sorted(psutil.process_iter(["name", "cpu_percent", "memory_percent"]),
                               key=lambda p: p.info["cpu_percent"] or 0, reverse=True)[:5]
                data["top_processes"] = [
                    {"name": p.info["name"], "cpu": p.info["cpu_percent"]}
                    for p in procs
                ]
            return json.dumps(data, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"Error obteniendo info: {e}"

    def get_cpu(self) -> int:
        if not PSUTIL_OK:
            return 0
        try:
            return int(psutil.cpu_percent(interval=None))
        except Exception:
            return 0

    def get_ram(self) -> int:
        if not PSUTIL_OK:
            return 0
        try:
            return int(psutil.virtual_memory().percent)
        except Exception:
            return 0

    def media_control(self, action: str) -> str:
        """Controla la reproducción de música usando teclas multimedia virtuales."""
        if not PYAUTOGUI_OK:
            return "pyautogui no disponible."
        try:
            import pyautogui
            mapping = {
                "play_pause": "playpause",
                "next": "nexttrack",
                "prev": "prevtrack"
            }
            key = mapping.get(action.lower().strip())
            if not key:
                return f"Acción de reproducción '{action}' no soportada."
            pyautogui.press(key)
            return f"Reproducción: ejecutada acción '{action}'."
        except Exception as e:
            return f"Error controlando medios: {e}"

    def window_control(self, action: str) -> str:
        """Controla las ventanas activas de Windows emulando atajos de teclado."""
        if not PYAUTOGUI_OK:
            return "pyautogui no disponible."
        try:
            import pyautogui
            act = action.lower().strip()
            if act == "minimize_all":
                pyautogui.hotkey("win", "d")
                return "Escritorio: todas las ventanas minimizadas."
            elif act == "close_active":
                pyautogui.hotkey("alt", "f4")
                return "Ventana: cerrada la ventana activa."
            elif act == "maximize_active":
                pyautogui.hotkey("win", "up")
                return "Ventana: maximizada la ventana activa."
            elif act == "split_left":
                pyautogui.hotkey("win", "left")
                return "Ventana: acoplada a la izquierda."
            elif act == "split_right":
                pyautogui.hotkey("win", "right")
                return "Ventana: acoplada a la derecha."
            return f"Acción de ventana '{action}' no reconocida."
        except Exception as e:
            return f"Error controlando ventana: {e}"

    def lock_screen(self) -> str:
        """Bloquea la PC con la API de Windows."""
        try:
            import ctypes
            ctypes.windll.user32.LockWorkStation()
            return "Sistema bloqueado correctamente."
        except Exception as e:
            return f"No se pudo bloquear la PC: {e}"

    def suspend_pc(self) -> str:
        """Suspende la PC con comandos nativos de Windows."""
        try:
            import os
            os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
            return "PC suspendida correctamente."
        except Exception as e:
            return f"No se pudo suspender la PC: {e}"

    def restart_pc(self) -> str:
        """Reinicia la PC con comando nativo."""
        try:
            import os
            os.system("shutdown /r /t 1")
            return "Reiniciando la PC..."
        except Exception as e:
            return f"No se pudo reiniciar la PC: {e}"

    def shutdown_pc(self) -> str:
        """Apaga la PC con comando nativo."""
        try:
            import os
            os.system("shutdown /s /t 1")
            return "Apagando la PC..."
        except Exception as e:
            return f"No se pudo apagar la PC: {e}"

    def play_spotify(self, query: str) -> str:
        """Busca y reproduce contenido en Spotify abriendo la URL de búsqueda."""
        try:
            import webbrowser
            import urllib.parse
            encoded = urllib.parse.quote(query)
            url = f"https://open.spotify.com/search/{encoded}"
            webbrowser.open(url)
            return f"Buscando '{query}' en Spotify..."
        except Exception as e:
            return f"No se pudo buscar en Spotify: {e}"

