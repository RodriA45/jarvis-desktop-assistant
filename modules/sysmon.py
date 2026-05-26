"""
SysMonitor — Thread en background que envía métricas reales al HUD cada 2s.
Incluye alertas automáticas cuando CPU > 90% o RAM > 85%.
"""
import threading
import time

try:
    import psutil
    PSUTIL_OK = True
except ImportError:
    PSUTIL_OK = False


def _get_gpu_stats():
    import subprocess
    import os
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        cmd = ["nvidia-smi", "--query-gpu=utilization.gpu,temperature.gpu", "--format=csv,noheader,nounits"]
        res = subprocess.run(cmd, capture_output=True, text=True, startupinfo=startupinfo, timeout=2)
        if res.returncode == 0:
            parts = res.stdout.strip().split(",")
            if len(parts) >= 2:
                gpu_load = int(parts[0].strip())
                gpu_temp = int(parts[1].strip())
                return gpu_load, gpu_temp
    except Exception:
        pass
        
    try:
        path = r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe"
        if os.path.exists(path):
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            cmd = [path, "--query-gpu=utilization.gpu,temperature.gpu", "--format=csv,noheader,nounits"]
            res = subprocess.run(cmd, capture_output=True, text=True, startupinfo=startupinfo, timeout=2)
            if res.returncode == 0:
                parts = res.stdout.strip().split(",")
                if len(parts) >= 2:
                    gpu_load = int(parts[0].strip())
                    gpu_temp = int(parts[1].strip())
                    return gpu_load, gpu_temp
    except Exception:
        pass
        
    return None, None


class SysMonitor:
    def __init__(self, hud=None, on_alert: callable = None):
        self._hud = hud
        self._on_alert = on_alert  # callback(msg) para voz
        self._running = False
        self._thread = None
        self._last_alert_cpu = 0
        self._last_alert_ram = 0

    def start(self):
        if not PSUTIL_OK:
            print("[SYSMON] psutil no disponible — monitor desactivado.")
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print("[SYSMON] Monitor de sistema iniciado.")

    def stop(self):
        self._running = False

    def _loop(self):
        while self._running:
            try:
                cpu = psutil.cpu_percent(interval=1)
                mem = psutil.virtual_memory()
                ram = mem.percent

                # red
                net1 = psutil.net_io_counters()
                time.sleep(1)
                net2 = psutil.net_io_counters()
                tx_mb = round((net2.bytes_sent - net1.bytes_sent) / 1024 / 1024, 2)
                rx_mb = round((net2.bytes_recv - net1.bytes_recv) / 1024 / 1024, 2)

                # disco
                disk = psutil.disk_usage("/")
                disk_pct = disk.percent

                # temperatura (si hay sensores)
                temp = None
                try:
                    temps = psutil.sensors_temperatures()
                    if temps:
                        for key in ("coretemp", "cpu_thermal", "k10temp", "acpitz"):
                            if key in temps and temps[key]:
                                temp = temps[key][0].current
                                break
                except Exception:
                    pass

                gpu_load, gpu_temp = _get_gpu_stats()

                # actualizar HUD
                if self._hud:
                    self._hud.update_metrics_full(
                        cpu=int(cpu),
                        ram=int(ram),
                        disk=int(disk_pct),
                        tx=tx_mb,
                        rx=rx_mb,
                        temp=temp,
                        gpu_load=gpu_load,
                        gpu_temp=gpu_temp
                    )

                # alertas
                now = time.time()
                if cpu > 90 and now - self._last_alert_cpu > 60:
                    self._last_alert_cpu = now
                    msg = f"Alerta: CPU al {int(cpu)} por ciento."
                    if self._hud:
                        self._hud.add_log("warn", f"CPU CRÍTICO: {int(cpu)}%")
                    if self._on_alert:
                        self._on_alert(msg)

                if ram > 85 and now - self._last_alert_ram > 60:
                    self._last_alert_ram = now
                    msg = f"Alerta: memoria RAM al {int(ram)} por ciento."
                    if self._hud:
                        self._hud.add_log("warn", f"RAM ALTA: {int(ram)}%")
                    if self._on_alert:
                        self._on_alert(msg)

            except Exception as e:
                print(f"[SYSMON] Error: {e}")
                time.sleep(2)
