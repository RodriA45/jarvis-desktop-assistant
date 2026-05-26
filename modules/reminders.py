"""
ReminderSystem — Recordatorios y alarmas con voz.
Usa threading puro para evitar deps pesadas.
"""
import threading
import time
import datetime
import re
from typing import Callable


class Reminder:
    def __init__(self, rid, text, trigger_time, repeat_seconds=None):
        self.id = rid
        self.text = text
        self.trigger_time = trigger_time
        self.repeat_seconds = repeat_seconds
        self.fired = False


class ReminderSystem:
    def __init__(self, on_remind: Callable = None):
        self._reminders = {}
        self._next_id = 1
        self._on_remind = on_remind  # callback(text) cuando dispara
        self._lock = threading.Lock()
        self._running = True
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def add(self, text: str, seconds_from_now: float = None,
            at_time: datetime.datetime = None, repeat_seconds: float = None) -> int:
        if seconds_from_now is not None:
            trigger = time.time() + seconds_from_now
        elif at_time is not None:
            trigger = at_time.timestamp()
        else:
            return -1

        with self._lock:
            rid = self._next_id
            self._next_id += 1
            self._reminders[rid] = Reminder(rid, text, trigger, repeat_seconds)
        print(f"[REMINDER] #{rid} registrado: '{text}' en {seconds_from_now or '?'}s")
        return rid

    def remove(self, rid: int):
        with self._lock:
            self._reminders.pop(rid, None)

    def list_all(self) -> list:
        with self._lock:
            result = []
            for r in self._reminders.values():
                remaining = max(0, r.trigger_time - time.time())
                result.append({
                    "id": r.id,
                    "text": r.text,
                    "remaining_seconds": int(remaining),
                    "repeat": r.repeat_seconds
                })
            return result

    def _loop(self):
        while self._running:
            now = time.time()
            to_fire = []
            to_remove = []
            with self._lock:
                for rid, r in self._reminders.items():
                    if now >= r.trigger_time:
                        to_fire.append(r)
                        if r.repeat_seconds:
                            r.trigger_time = now + r.repeat_seconds
                        else:
                            to_remove.append(rid)
                for rid in to_remove:
                    del self._reminders[rid]

            for r in to_fire:
                print(f"[REMINDER] ¡Disparando! {r.text}")
                if self._on_remind:
                    threading.Thread(target=self._on_remind, args=(r.text,), daemon=True).start()

            time.sleep(1)

    def stop(self):
        self._running = False


def parse_reminder_from_text(text: str):
    """
    Parsea lenguaje natural para extraer: mensaje, tiempo en segundos, repetición.
    Ejemplos:
      "recordame tomar agua cada hora"
      "avisame en 30 minutos que hay reunión"
      "recordame en 2 horas cerrar el trabajo"
    Retorna dict {text, seconds, repeat} o None si no parsea.
    """
    text = text.lower()

    # repetición
    repeat = None
    rep_m = re.search(r"cada\s+(\d+)?\s*(segundo|minuto|hora|día|dia)", text)
    if rep_m:
        num = int(rep_m.group(1)) if rep_m.group(1) else 1
        unit = rep_m.group(2)
        mults = {"segundo": 1, "minuto": 60, "hora": 3600, "día": 86400, "dia": 86400}
        repeat = num * mults.get(unit, 60)

    # tiempo único
    seconds = None
    m = re.search(r"en\s+(\d+)\s*(segundo|minuto|hora)", text)
    if m:
        num = int(m.group(1))
        unit = m.group(2)
        mults = {"segundo": 1, "minuto": 60, "hora": 3600}
        seconds = num * mults.get(unit, 60)
    elif repeat:
        seconds = repeat  # primera vez = mismo intervalo

    if seconds is None and repeat is None:
        return None

    # mensaje: todo lo que viene después de "que" o la tarea
    msg_m = re.search(r"que\s+(.+?)(?:\s+en\s+\d|\s+cada\s+|$)", text)
    if msg_m:
        msg = msg_m.group(1).strip()
    else:
        # fallback: extraer la razón del recordatorio
        msg = re.sub(r"(recordame|avisame|remind me|cada\s+\d*\s*\w+|en\s+\d+\s*\w+)", "", text).strip()
        msg = msg or "Recordatorio"

    return {"text": msg.capitalize(), "seconds": seconds or 60, "repeat": repeat}
