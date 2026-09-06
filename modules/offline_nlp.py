"""
OfflineNLPController — Encapsula la lógica conversacional del modo sin conexión (demo).
Permite mantener `brain.py` limpio.
"""
import asyncio
import datetime
import re

class OfflineNLPController:
    def __init__(self, hud=None):
        self.hud = hud

    def process_offline(self, history: list, LLMBlock_cls, LLMResponse_cls):
        """
        Interpreta comandos en modo local usando NLP basado en Regex.
        :param history: El historial de la conversación.
        :param LLMBlock_cls: Referencia a la clase LLMBlock para construir respuestas.
        :param LLMResponse_cls: Referencia a la clase LLMResponse para empaquetar resultados.
        """
        # Tomar el último mensaje del usuario
        user_msg = ""
        for h in reversed(history):
            if h.get("role") == "user" and isinstance(h.get("content"), str):
                user_msg = h["content"].lower().strip()
                break

        # Verificar si es la segunda vuelta (después de ejecutar herramienta)
        if history:
            last_item = history[-1]
            if last_item.get("role") == "user" and isinstance(last_item.get("content"), list):
                # Es el resultado de la herramienta, devolvemos confirmación o resumen
                tool_res = last_item["content"][0].get("content", "")
                clean_res = str(tool_res).replace("\n", " ").strip()
                # Si viene de una búsqueda web, formatearlo de forma más natural
                if "duckduckgo-search no instalado" in clean_res.lower() or "error en búsqueda" in clean_res.lower():
                    return LLMResponse_cls([LLMBlock_cls("text", text=f"Señor, no pude completar la búsqueda web. {clean_res}")], "end_turn")
                
                # Cortar resultados si son muy largos
                if len(clean_res) > 300:
                    clean_res = clean_res[:297] + "..."
                return LLMResponse_cls([LLMBlock_cls("text", text=f"He buscado en internet, señor. Aquí tiene el resultado: {clean_res}")], "end_turn")

        # Reglas NLP básicas para modo demostración
        # 1. Aplicaciones
        if "chrome" in user_msg or "google" in user_msg or "navegador" in user_msg:
            return LLMResponse_cls([LLMBlock_cls("tool_use", id="open_app_chrome", name="open_application", input={"app_name": "chrome"})], "tool_use")
        elif "bloc de notas" in user_msg or "notepad" in user_msg or "abri bloc" in user_msg:
            return LLMResponse_cls([LLMBlock_cls("tool_use", id="open_app_notepad", name="open_application", input={"app_name": "notepad"})], "tool_use")
        elif "spotify" in user_msg or "musica" in user_msg or "reproduci" in user_msg or "reproduce" in user_msg:
            query = ""
            for verb in ["reproduci en spotify", "reproduce en spotify", "busca en spotify", "reproduci", "reproduce", "spotify"]:
                if user_msg.startswith(verb):
                    query = user_msg[len(verb):].strip()
                    break
            if not query:
                m = re.search(r"(?:reproduci|reproduce|busca|escuchar)\s+(?:a\s+|en\s+spotify\s+|la\s+cancion\s+|la\s+canción\s+)?(.+)", user_msg)
                if m:
                    query = m.group(1).strip()
            
            if query and "musica" not in query:
                return LLMResponse_cls([LLMBlock_cls("tool_use", id="spotify_play", name="open_url", input={"url": f"spotify_search:{query}"})], "tool_use")
            else:
                return LLMResponse_cls([LLMBlock_cls("tool_use", id="open_app_spotify", name="open_application", input={"app_name": "spotify"})], "tool_use")
        elif "calculadora" in user_msg:
            return LLMResponse_cls([LLMBlock_cls("tool_use", id="open_app_calc", name="open_application", input={"app_name": "calc"})], "tool_use")
        elif "consola" in user_msg or "terminal" in user_msg or "cmd" in user_msg:
            return LLMResponse_cls([LLMBlock_cls("tool_use", id="open_app_term", name="open_application", input={"app_name": "terminal"})], "tool_use")
        elif "escribi" in user_msg or "tipea" in user_msg:
            match = re.search(r"(?:escribi|tipea)\s+(.+)", user_msg)
            text_to_type = match.group(1) if match else "Hola mundo"
            return LLMResponse_cls([LLMBlock_cls("tool_use", id="type_text_cmd", name="type_text", input={"text": text_to_type})], "tool_use")
        
        # 2. Volumen
        elif "volumen" in user_msg or "sonido" in user_msg:
            if "subi" in user_msg or "aumenta" in user_msg:
                return LLMResponse_cls([LLMBlock_cls("tool_use", id="vol_up", name="control_volume", input={"action": "up"})], "tool_use")
            elif "baja" in user_msg or "disminui" in user_msg:
                return LLMResponse_cls([LLMBlock_cls("tool_use", id="vol_down", name="control_volume", input={"action": "down"})], "tool_use")
            elif "silencia" in user_msg or "mute" in user_msg or "desactiva" in user_msg:
                return LLMResponse_cls([LLMBlock_cls("tool_use", id="vol_mute", name="control_volume", input={"action": "mute"})], "tool_use")
            elif "activa" in user_msg or "unmute" in user_msg:
                return LLMResponse_cls([LLMBlock_cls("tool_use", id="vol_unmute", name="control_volume", input={"action": "unmute"})], "tool_use")
            else:
                nums = re.findall(r"\d+", user_msg)
                val = int(nums[0]) if nums else 50
                return LLMResponse_cls([LLMBlock_cls("tool_use", id="vol_set", name="control_volume", input={"action": "set", "value": val})], "tool_use")
        
        # 3. Multimedia
        elif "pausa" in user_msg or "reproduce" in user_msg or "musica" in user_msg:
            return LLMResponse_cls([LLMBlock_cls("tool_use", id="media_play", name="media_control", input={"action": "play_pause"})], "tool_use")
        elif "siguiente" in user_msg or "proxima" in user_msg:
            return LLMResponse_cls([LLMBlock_cls("tool_use", id="media_next", name="media_control", input={"action": "next"})], "tool_use")
        elif "anterior" in user_msg:
            return LLMResponse_cls([LLMBlock_cls("tool_use", id="media_prev", name="media_control", input={"action": "prev"})], "tool_use")
        
        # 4. Ventanas
        elif "minimiza todo" in user_msg or "escritorio" in user_msg or "minimiza las ventanas" in user_msg:
            return LLMResponse_cls([LLMBlock_cls("tool_use", id="win_min", name="window_control", input={"action": "minimize_all"})], "tool_use")
        elif "cierra" in user_msg or "cerra la ventana" in user_msg or "cerra programa" in user_msg:
            return LLMResponse_cls([LLMBlock_cls("tool_use", id="win_close", name="window_control", input={"action": "close_active"})], "tool_use")
        elif "acopla a la izquierda" in user_msg or "pantalla izquierda" in user_msg:
            return LLMResponse_cls([LLMBlock_cls("tool_use", id="win_left", name="window_control", input={"action": "split_left"})], "tool_use")
        elif "acopla a la derecha" in user_msg or "pantalla derecha" in user_msg:
            return LLMResponse_cls([LLMBlock_cls("tool_use", id="win_right", name="window_control", input={"action": "split_right"})], "tool_use")
        
        # 5. Capturas
        elif "captura" in user_msg or "foto de pantalla" in user_msg:
            return LLMResponse_cls([LLMBlock_cls("tool_use", id="screenshot_cmd", name="take_screenshot", input={"analyze": False})], "tool_use")
        
        # 6. Telemetría / Sistema
        elif any(w in user_msg for w in ["bloquear la pc", "bloquea la pc", "bloquear pc", "bloquea pc", "bloquear pantalla", "bloquear la computadora", "bloquea la computadora"]):
            return LLMResponse_cls([LLMBlock_cls("tool_use", id="sys_lock", name="run_command", input={"command": "lock"})], "tool_use")
        elif any(w in user_msg for w in ["suspender la pc", "suspender pc", "suspende pc", "suspender la computadora", "suspende la computadora", "suspende la pc"]):
            return LLMResponse_cls([LLMBlock_cls("tool_use", id="sys_suspend", name="run_command", input={"command": "suspend"})], "tool_use")
        elif any(w in user_msg for w in ["reiniciar la pc", "reiniciar pc", "reinicia pc", "reiniciar la computadora", "reinicia la computadora"]):
            return LLMResponse_cls([LLMBlock_cls("tool_use", id="sys_restart", name="run_command", input={"command": "restart"})], "tool_use")
        elif any(w in user_msg for w in ["apagar la pc", "apagar pc", "apaga pc", "apagar la computadora", "apaga la computadora"]):
            return LLMResponse_cls([LLMBlock_cls("tool_use", id="sys_shutdown", name="run_command", input={"command": "shutdown"})], "tool_use")
        elif "sistema" in user_msg or "recursos" in user_msg or "cpu" in user_msg or "ram" in user_msg or "gpu" in user_msg or "disco" in user_msg:
            return LLMResponse_cls([LLMBlock_cls("tool_use", id="sys_info_cmd", name="get_system_info", input={"info_type": "all"})], "tool_use")
        
        # 7. Clima y búsqueda de información general offline (DuckDuckGo integration)
        elif any(w in user_msg for w in ["clima", "tiempo", "temperatura", "dia hoy", "día hoy"]):
            # Buscar el clima de hoy por DuckDuckGo
            return LLMResponse_cls([LLMBlock_cls("tool_use", id="web_search_clima", name="web_search", input={"query": "clima de hoy"})], "tool_use")
        elif any(w in user_msg for w in ["busca", "buscar", "quien es", "qué es", "que es"]):
            query = user_msg
            for verb in ["busca", "buscar", "quien es", "qué es", "que es"]:
                if query.startswith(verb):
                    query = query[len(verb):].strip()
            return LLMResponse_cls([LLMBlock_cls("tool_use", id="web_search_general", name="web_search", input={"query": query})], "tool_use")
        
        # 8. Hora y Fecha offline
        elif "hora" in user_msg:
            now_time = datetime.datetime.now().strftime("%H:%M")
            return LLMResponse_cls([LLMBlock_cls("text", text=f"Son las {now_time}, señor.")], "end_turn")
        elif any(w in user_msg for w in ["fecha", "día de hoy", "dia de hoy", "que dia es", "qué día es", "dia es"]):
            dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
            meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
            now = datetime.datetime.now()
            dia_semana = dias[now.weekday()]
            mes = meses[now.month - 1]
            fecha_str = f"Hoy es {dia_semana} {now.day} de {mes} de {now.year}."
            return LLMResponse_cls([LLMBlock_cls("text", text=fecha_str)], "end_turn")
        
        # 9. Apagado offline por voz
        elif any(w in user_msg for w in ["apagar jarvis", "cerrar jarvis", "cerrate", "apagate"]):
            if self.hud:
                self.hud.add_log("warn", "Apagando por comando de voz...")
                loop = asyncio.get_event_loop()
                loop.call_soon_threadsafe(self.hud.shutdown)
            return LLMResponse_cls([LLMBlock_cls("text", text="Entendido, cerrando sistemas de inmediato. Hasta luego, señor.")], "end_turn")
        
        # 10. Respuestas generales
        else:
            respuestas = {
                "hola": "Hola señor, estoy operando en modo demostración offline. ¿En qué puedo ayudarlo?",
                "como estas": "Todos mis sistemas están estables en modo offline, señor.",
                "quien sos": "Soy J.A.R.V.I.S., su asistente de IA personal para Windows.",
                "gracias": "De nada, señor. Es un placer."
            }
            for k, v in respuestas.items():
                if k in user_msg:
                    return LLMResponse_cls([LLMBlock_cls("text", text=v)], "end_turn")
            
            return LLMResponse_cls([LLMBlock_cls("text", text="Entendido, señor. Estoy en modo offline de demostración (sin API keys). Puedo controlar volumen, ventanas, abrir aplicaciones o reproducir música si me lo pide.")], "end_turn")
