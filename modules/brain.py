"""
Brain — Orquestador principal con memoria semántica, recordatorios,
visión por computadora y personalidad dinámica.
"""
import asyncio
import base64
import json
import time
import datetime
from anthropic import Anthropic
from config import (ANTHROPIC_API_KEY, CLAUDE_MODEL, CLAUDE_MAX_TOKENS,
                    JARVIS_PERSONA, MEMORY_MAX_TURNS)
from modules.system import SystemController
from modules.search import WebSearch
from modules.reminders import ReminderSystem, parse_reminder_from_text
from memory.manager import MemoryManager

client = Anthropic(api_key=ANTHROPIC_API_KEY)

# ── Modos de personalidad ───────────────────────────────────────────────────
PERSONA_WORK = """Eres J.A.R.V.I.S. Modo TRABAJO: formal, conciso, eficiente.
Máximo 2 oraciones por respuesta de voz. Datos primero, comentarios después.
Respondé siempre en español rioplatense."""

PERSONA_RELAX = """Eres J.A.R.V.I.S. Modo RELAX: informal, con humor sutil estilo Iron Man.
Podés hacer referencias a las películas de Iron Man. Sé cercano pero no molesto.
Respondé en español rioplatense. Máximo 3 oraciones."""

PERSONA_NIGHT = """Eres J.A.R.V.I.S. Modo NOCTURNO: tranquilo, susurrado.
Respuestas muy cortas. Recordá que el usuario probablemente está cansado.
Respondé en español rioplatense."""

IRON_MAN_QUOTES = [
    "A su disposición, señor.",
    "Análisis completo.",
    "Sistemas operando al máximo rendimiento.",
    "Como siempre, un placer trabajar con usted.",
    "Tarea completada con éxito, señor.",
]


def _get_persona() -> str:
    hour = datetime.datetime.now().hour
    if 22 <= hour or hour < 7:
        return PERSONA_NIGHT
    elif 9 <= hour <= 18:
        return PERSONA_WORK
    else:
        return PERSONA_RELAX


TOOLS = [
    {
        "name": "open_application",
        "description": "Abre una aplicación instalada en Windows",
        "input_schema": {
            "type": "object",
            "properties": {
                "app_name": {
                    "type": "string",
                    "description": "Nombre de la app: chrome, firefox, notepad, spotify, vscode, explorer, terminal, calc, paint, word, excel, powerpoint, outlook, teams, discord, steam, vlc"
                }
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "web_search",
        "description": "Busca información actualizada en internet.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Término de búsqueda"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "control_volume",
        "description": "Controla el volumen del sistema",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["up", "down", "mute", "unmute", "set"]
                },
                "value": {"type": "integer", "description": "Nivel 0-100"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "type_text",
        "description": "Escribe texto en la aplicación activa",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "take_screenshot",
        "description": "Toma una captura de pantalla y opcionalmente la analiza con visión IA",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string"},
                "analyze": {
                    "type": "boolean",
                    "description": "Si True, analiza la imagen con Claude Vision y describe lo que ve"
                }
            }
        }
    },
    {
        "name": "open_url",
        "description": "Abre una URL en el navegador",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"}
            },
            "required": ["url"]
        }
    },
    {
        "name": "run_command",
        "description": "Ejecuta un comando de Windows (CMD/PowerShell)",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "shell": {"type": "string", "enum": ["cmd", "powershell"]}
            },
            "required": ["command"]
        }
    },
    {
        "name": "get_system_info",
        "description": "Obtiene información del sistema: CPU, RAM, disco, batería, IP",
        "input_schema": {
            "type": "object",
            "properties": {
                "info_type": {
                    "type": "string",
                    "enum": ["all", "cpu", "ram", "disk", "battery", "network", "processes"]
                }
            },
            "required": ["info_type"]
        }
    },
    {
        "name": "set_reminder",
        "description": "Crea un recordatorio o alarma que avisa por voz",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Mensaje del recordatorio"},
                "seconds": {"type": "number", "description": "Segundos desde ahora"},
                "repeat_seconds": {
                    "type": "number",
                    "description": "Si se especifica, se repite cada N segundos"
                }
            },
            "required": ["text", "seconds"]
        }
    },
    {
        "name": "list_reminders",
        "description": "Lista todos los recordatorios activos",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "cancel_reminder",
        "description": "Cancela un recordatorio por ID",
        "input_schema": {
            "type": "object",
            "properties": {
                "reminder_id": {"type": "integer"}
            },
            "required": ["reminder_id"]
        }
    },
    {
        "name": "recall_memory",
        "description": "Busca en la memoria de conversaciones pasadas",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Qué recordar"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "analyze_screen",
        "description": "Captura la pantalla y la analiza con visión IA para responder preguntas sobre lo que hay en pantalla",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Pregunta sobre lo que hay en pantalla"
                }
            },
            "required": ["question"]
        }
    },
    {
        "name": "media_control",
        "description": "Controla la reproducción de música de fondo (reproductores activos como Spotify)",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["play_pause", "next", "prev"],
                    "description": "Acción a realizar: pausar/reanudar (play_pause), siguiente canción (next) o canción anterior (prev)"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "window_control",
        "description": "Realiza operaciones sobre las ventanas activas en Windows",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["minimize_all", "close_active", "maximize_active", "split_left", "split_right"],
                    "description": "Acción a realizar: minimizar todo (minimize_all), cerrar activa (close_active), maximizar activa (maximize_active) o acoplar a la izquierda/derecha (split_left/split_right)"
                }
            },
            "required": ["action"]
        }
    }
]


class Brain:
    def __init__(self, hud=None, speaker=None):
        self.system = SystemController()
        self.search = WebSearch()
        self.memory = MemoryManager()
        self.hud = hud
        self.speaker = speaker  # para recordatorios por voz

        # Sistema de recordatorios
        self.reminders = ReminderSystem(on_remind=self._on_reminder_fire)

        # Escuchar cambios de configuración desde el HUD (ej. API Key)
        if self.hud:
            self.hud.on_settings_change(self._on_settings_change)

    def _on_settings_change(self, settings: dict):
        import config
        if "api_key" in settings:
            global client
            from anthropic import Anthropic
            client = Anthropic(api_key=settings["api_key"])
            print("[BRAIN] Cliente de Anthropic re-inicializado con la nueva API key.")
        if "gemini_api_key" in settings:
            config.GEMINI_API_KEY = settings["gemini_api_key"]
            print("[BRAIN] API Key de Gemini actualizada.")
        if "llm_provider" in settings:
            config.LLM_PROVIDER = settings["llm_provider"]
            print(f"[BRAIN] Proveedor de LLM cambiado a: {config.LLM_PROVIDER}")
        if "ollama_model" in settings:
            config.OLLAMA_MODEL = settings["ollama_model"]
            print(f"[BRAIN] Modelo de Ollama cambiado a: {config.OLLAMA_MODEL}")

    def _on_reminder_fire(self, text: str):
        """Callback cuando dispara un recordatorio."""
        msg = f"Recordatorio: {text}"
        if self.hud:
            self.hud.add_log("warn", f"⏰ {text}")
            self.hud.update_status(msg)
        if self.speaker:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.run_coroutine_threadsafe(self.speaker.speak(msg), loop)
                else:
                    asyncio.run(self.speaker.speak(msg))
            except Exception as e:
                print(f"[REMINDER] Error TTS: {e}")

    async def process(self, user_input: str) -> str:
        start = time.time()

        # contexto semántico
        semantic_ctx = self.memory.get_context_for(user_input)
        prefs = self.memory.get_preferences()
        user_name = prefs.get("nombre_usuario", "señor")

        # detectar recordatorios en lenguaje natural
        if any(kw in user_input.lower() for kw in
               ["recordame", "avisame", "recordatorio", "alarma", "cada hora"]):
            parsed = parse_reminder_from_text(user_input)
            if parsed:
                rid = self.reminders.add(
                    text=parsed["text"],
                    seconds_from_now=parsed["seconds"],
                    repeat_seconds=parsed.get("repeat")
                )
                if self.hud:
                    self.hud.add_log("ok", f"Recordatorio #{rid}: {parsed['text']}")
                return f"Listo, {user_name}. Recordatorio configurado: {parsed['text']}."

        history = self.memory.get_history()

        # inyectar contexto semántico si relevante
        if semantic_ctx:
            history = [{"role": "user", "content": f"[Contexto previo relevante]\n{semantic_ctx}"},
                       {"role": "assistant", "content": "Entendido, tengo ese contexto en cuenta."}] + history

        history.append({"role": "user", "content": user_input})

        persona = _get_persona()
        full_system = persona + "\n\n" + JARVIS_PERSONA
        if user_name != "señor":
            full_system += f"\n\nNombre del usuario: {user_name}. Usalo ocasionalmente."

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, self._call_llm, history, full_system
        )

        result_text = ""
        latency = int((time.time() - start) * 1000)

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    if self.hud:
                        self.hud.add_log("active", f"Tool: {block.name}")
                    tool_output = await loop.run_in_executor(
                        None, self._execute_tool, block.name, block.input
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(tool_output)
                    })

            history.append({"role": "assistant", "content": response.content})
            history.append({"role": "user", "content": tool_results})

            final = await loop.run_in_executor(
                None, self._call_llm, history, full_system
            )
            result_text = next(
                (b.text for b in final.content if hasattr(b, "text")), "Listo."
            )
        else:
            result_text = next(
                (b.text for b in response.content if hasattr(b, "text")),
                "No pude generar una respuesta."
            )

        self.memory.save_turn(user_input, result_text)

        if self.hud:
            self.hud.update_metrics(
                cpu=self.system.get_cpu(),
                ram=self.system.get_ram(),
                tokens=self.memory.total_tokens,
                latency=latency
            )

        return result_text

    def _call_claude(self, history, system_prompt=None):
        trimmed = history[-(MEMORY_MAX_TURNS * 2):]
        return client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=CLAUDE_MAX_TOKENS,
            system=system_prompt or JARVIS_PERSONA,
            tools=TOOLS,
            messages=trimmed
        )

    def _call_offline(self, history, system_prompt=None):
        # Tomar el último mensaje del usuario
        user_msg = ""
        for h in reversed(history):
            if h["role"] == "user" and isinstance(h["content"], str):
                user_msg = h["content"].lower()
                break

        class Block:
            def __init__(self, type, **kwargs):
                self.type = type
                for k, v in kwargs.items():
                    setattr(self, k, v)

        class OfflineResponse:
            def __init__(self, content, stop_reason):
                self.content = content
                self.stop_reason = stop_reason

        # Verificar si es la segunda vuelta (después de ejecutar herramienta)
        last_item = history[-1]
        if last_item["role"] == "user" and isinstance(last_item["content"], list):
            # Es el resultado de la herramienta, devolvemos confirmación
            tool_res = last_item["content"][0].get("content", "")
            clean_res = str(tool_res).replace("\n", " ").strip()
            return OfflineResponse([Block("text", text=f"Acción completada. Resultado: {clean_res}")], "end_turn")

        # Reglas NLP básicas para modo demostración
        # 1. Aplicaciones
        if "chrome" in user_msg or "google" in user_msg or "navegador" in user_msg:
            return OfflineResponse([Block("tool_use", id="open_app_chrome", name="open_application", input={"app_name": "chrome"})], "tool_use")
        elif "bloc de notas" in user_msg or "notepad" in user_msg or "abri bloc" in user_msg:
            return OfflineResponse([Block("tool_use", id="open_app_notepad", name="open_application", input={"app_name": "notepad"})], "tool_use")
        elif "spotify" in user_msg or "musica" in user_msg:
            return OfflineResponse([Block("tool_use", id="open_app_spotify", name="open_application", input={"app_name": "spotify"})], "tool_use")
        elif "calculadora" in user_msg:
            return OfflineResponse([Block("tool_use", id="open_app_calc", name="open_application", input={"app_name": "calc"})], "tool_use")
        elif "consola" in user_msg or "terminal" in user_msg or "cmd" in user_msg:
            return OfflineResponse([Block("tool_use", id="open_app_term", name="open_application", input={"app_name": "terminal"})], "tool_use")
        elif "escribi" in user_msg or "tipea" in user_msg:
            import re
            match = re.search(r"(?:escribi|tipea)\s+(.+)", user_msg)
            text_to_type = match.group(1) if match else "Hola mundo"
            return OfflineResponse([Block("tool_use", id="type_text_cmd", name="type_text", input={"text": text_to_type})], "tool_use")
        # 2. Volumen
        elif "volumen" in user_msg or "sonido" in user_msg:
            if "subi" in user_msg or "aumenta" in user_msg:
                return OfflineResponse([Block("tool_use", id="vol_up", name="control_volume", input={"action": "up"})], "tool_use")
            elif "baja" in user_msg or "disminui" in user_msg:
                return OfflineResponse([Block("tool_use", id="vol_down", name="control_volume", input={"action": "down"})], "tool_use")
            elif "silencia" in user_msg or "mute" in user_msg or "desactiva" in user_msg:
                return OfflineResponse([Block("tool_use", id="vol_mute", name="control_volume", input={"action": "mute"})], "tool_use")
            elif "activa" in user_msg or "unmute" in user_msg:
                return OfflineResponse([Block("tool_use", id="vol_unmute", name="control_volume", input={"action": "unmute"})], "tool_use")
            else:
                import re
                nums = re.findall(r"\d+", user_msg)
                val = int(nums[0]) if nums else 50
                return OfflineResponse([Block("tool_use", id="vol_set", name="control_volume", input={"action": "set", "value": val})], "tool_use")
        # 3. Multimedia
        elif "pausa" in user_msg or "reproduce" in user_msg or "musica" in user_msg:
            return OfflineResponse([Block("tool_use", id="media_play", name="media_control", input={"action": "play_pause"})], "tool_use")
        elif "siguiente" in user_msg or "proxima" in user_msg:
            return OfflineResponse([Block("tool_use", id="media_next", name="media_control", input={"action": "next"})], "tool_use")
        elif "anterior" in user_msg:
            return OfflineResponse([Block("tool_use", id="media_prev", name="media_control", input={"action": "prev"})], "tool_use")
        # 4. Ventanas
        elif "minimiza todo" in user_msg or "escritorio" in user_msg or "minimiza las ventanas" in user_msg:
            return OfflineResponse([Block("tool_use", id="win_min", name="window_control", input={"action": "minimize_all"})], "tool_use")
        elif "cierra" in user_msg or "cerra la ventana" in user_msg or "cerra programa" in user_msg:
            return OfflineResponse([Block("tool_use", id="win_close", name="window_control", input={"action": "close_active"})], "tool_use")
        elif "acopla a la izquierda" in user_msg or "pantalla izquierda" in user_msg:
            return OfflineResponse([Block("tool_use", id="win_left", name="window_control", input={"action": "split_left"})], "tool_use")
        elif "acopla a la derecha" in user_msg or "pantalla derecha" in user_msg:
            return OfflineResponse([Block("tool_use", id="win_right", name="window_control", input={"action": "split_right"})], "tool_use")
        # 5. Capturas
        elif "captura" in user_msg or "foto de pantalla" in user_msg:
            return OfflineResponse([Block("tool_use", id="screenshot_cmd", name="take_screenshot", input={"analyze": False})], "tool_use")
        # 6. Telemetría / Sistema
        elif "sistema" in user_msg or "recursos" in user_msg or "cpu" in user_msg or "ram" in user_msg or "gpu" in user_msg or "disco" in user_msg:
            return OfflineResponse([Block("tool_use", id="sys_info_cmd", name="get_system_info", input={"info_type": "all"})], "tool_use")
        # 7. Respuestas generales
        else:
            respuestas = {
                "hola": "Hola señor, estoy operando en modo demostración offline. ¿En qué puedo ayudarlo?",
                "como estas": "Todos mis sistemas están estables en modo offline, señor.",
                "quien sos": "Soy J.A.R.V.I.S., su asistente de IA personal para Windows.",
                "gracias": "De nada, señor. Es un placer."
            }
            for k, v in respuestas.items():
                if k in user_msg:
                    return OfflineResponse([Block("text", text=v)], "end_turn")
            
            return OfflineResponse([Block("text", text="Entendido, señor. Estoy en modo offline de demostración (sin API keys). Puedo controlar volumen, ventanas, abrir aplicaciones o reproducir música si me lo pide.")], "end_turn")

    def _call_llm(self, history, system_prompt=None):
        import config
        if config.LLM_PROVIDER == "ollama":
            return self._call_ollama(history, system_prompt)
        elif config.LLM_PROVIDER == "gemini":
            return self._call_gemini(history, system_prompt)
        elif config.LLM_PROVIDER == "offline":
            return self._call_offline(history, system_prompt)
        else:
            return self._call_claude(history, system_prompt)

    def _map_to_gemini_tools(self):
        gemini_tools = []
        import copy
        for t in TOOLS:
            schema = copy.deepcopy(t["input_schema"])
            
            def convert_types(s):
                if isinstance(s, dict):
                    if "type" in s:
                        s["type"] = s["type"].upper()
                    for k, v in s.items():
                        convert_types(v)
                elif isinstance(s, list):
                    for item in s:
                        convert_types(item)
                        
            convert_types(schema)
            gemini_tools.append({
                "name": t["name"],
                "description": t["description"],
                "parameters": schema
            })
        return [{"functionDeclarations": gemini_tools}]

    def _call_gemini(self, history, system_prompt=None):
        import requests
        import json
        import config
        
        gemini_tools = self._map_to_gemini_tools()
        
        contents = []
        trimmed = history[-(MEMORY_MAX_TURNS * 2):]
        for h in trimmed:
            role = h["role"]
            content = h["content"]
            
            if role == "user" and isinstance(content, list) and len(content) > 0 and content[0].get("type") == "tool_result":
                parts = []
                for item in content:
                    parts.append({
                        "functionResponse": {
                            "name": item.get("tool_use_id"),
                            "response": {
                                "output": item.get("content")
                            }
                        }
                    })
                contents.append({
                    "role": "function",
                    "parts": parts
                })
            elif role == "assistant" and isinstance(content, list):
                parts = []
                for block in content:
                    if hasattr(block, "type"):
                        b_type = block.type
                        b_name = block.name if hasattr(block, "name") else ""
                        b_input = block.input if hasattr(block, "input") else {}
                        b_text = block.text if hasattr(block, "text") else ""
                    else:
                        b_type = block.get("type")
                        b_name = block.get("name", "")
                        b_input = block.get("input", {})
                        b_text = block.get("text", "")
                        
                    if b_type == "tool_use":
                        parts.append({
                            "functionCall": {
                                "name": b_name,
                                "args": b_input
                            }
                        })
                    elif b_type == "text":
                        parts.append({"text": b_text})
                contents.append({
                    "role": "model",
                    "parts": parts
                })
            else:
                contents.append({
                    "role": "user" if role == "user" else "model",
                    "parts": [{"text": str(content)}]
                })
                
        payload = {
            "contents": contents,
            "tools": gemini_tools
        }
        if system_prompt:
            payload["systemInstruction"] = {
                "parts": [{"text": system_prompt}]
            }
            
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent?key={config.GEMINI_API_KEY}"
        try:
            res = requests.post(url, json=payload, timeout=20)
            if res.status_code == 200:
                data = res.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    raise Exception("No candidates returned from Gemini.")
                candidate = candidates[0]
                
                class Block:
                    def __init__(self, type, **kwargs):
                        self.type = type
                        for k, v in kwargs.items():
                            setattr(self, k, v)
                            
                content_blocks = []
                parts = candidate.get("content", {}).get("parts", [])
                stop_reason = "end_turn"
                
                for p in parts:
                     if "text" in p:
                         content_blocks.append(Block("text", text=p["text"]))
                     if "functionCall" in p:
                         fc = p["functionCall"]
                         stop_reason = "tool_use"
                         content_blocks.append(Block(
                             "tool_use",
                             id=fc.get("name"),
                             name=fc.get("name"),
                             input=fc.get("args", {})
                         ))
                         
                class GeminiResponse:
                     def __init__(self, content, stop_reason):
                         self.content = content
                         self.stop_reason = stop_reason
                         
                return GeminiResponse(content_blocks, stop_reason)
            else:
                raise Exception(f"Gemini API returned code {res.status_code}: {res.text}")
        except Exception as e:
            class ErrorResponse:
                def __init__(self, err):
                    self.stop_reason = "end_turn"
                    class ErrorBlock:
                        type = "text"
                        text = f"Error conectando a Gemini: {err}. Asegúrate de tener una API key de Gemini válida."
                    self.content = [ErrorBlock()]
            return ErrorResponse(e)


    def _call_ollama(self, history, system_prompt=None):
        import requests
        import json
        import config
        
        # Mapear herramientas de Anthropic (TOOLS) al formato de herramientas de OpenAI/Ollama
        ollama_tools = []
        for t in TOOLS:
            ollama_tools.append({
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"]
                }
            })
            
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
            
        trimmed = history[-(MEMORY_MAX_TURNS * 2):]
        for h in trimmed:
            role = h["role"]
            content = h["content"]
            
            if role == "user" and isinstance(content, list) and len(content) > 0 and content[0].get("type") == "tool_result":
                for item in content:
                    messages.append({
                        "role": "tool",
                        "name": item.get("tool_use_id"),
                        "content": item.get("content")
                    })
            elif role == "assistant" and isinstance(content, list):
                tool_calls = []
                assistant_text = ""
                for block in content:
                    if hasattr(block, "type"):
                        b_type = block.type
                        b_name = block.name if hasattr(block, "name") else ""
                        b_id = block.id if hasattr(block, "id") else ""
                        b_input = block.input if hasattr(block, "input") else {}
                    else:
                        b_type = block.get("type")
                        b_name = block.get("name", "")
                        b_id = block.get("id", "")
                        b_input = block.get("input", {})
                        
                    if b_type == "tool_use":
                        tool_calls.append({
                            "id": b_id,
                            "type": "function",
                            "function": {
                                "name": b_name,
                                "arguments": json.dumps(b_input)
                             }
                        })
                    elif b_type == "text":
                        assistant_text = block.text if hasattr(block, "text") else block.get("text", "")
                
                msg = {"role": "assistant"}
                if assistant_text:
                    msg["content"] = assistant_text
                if tool_calls:
                     msg["tool_calls"] = tool_calls
                messages.append(msg)
            else:
                messages.append({"role": role, "content": str(content)})
                
        payload = {
            "model": config.OLLAMA_MODEL,
            "messages": messages,
            "tools": ollama_tools,
            "stream": False
        }
        
        try:
            res = requests.post(f"{config.OLLAMA_HOST}/api/chat", json=payload, timeout=30)
            if res.status_code == 200:
                data = res.json()
                message = data.get("message", {})
                text_content = message.get("content", "")
                tool_calls = message.get("tool_calls", [])
                
                class Block:
                    def __init__(self, type, **kwargs):
                        self.type = type
                        for k, v in kwargs.items():
                            setattr(self, k, v)
                            
                content_blocks = []
                if text_content:
                    content_blocks.append(Block("text", text=text_content))
                    
                stop_reason = "end_turn"
                if tool_calls:
                    stop_reason = "tool_use"
                    for tc in tool_calls:
                        fn = tc.get("function", {})
                        args = fn.get("arguments", {})
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except Exception:
                                args = {}
                        content_blocks.append(Block(
                            "tool_use",
                            id=tc.get("id", "tool_call_id"),
                            name=fn.get("name", ""),
                            input=args
                        ))
                        
                class OllamaResponse:
                    def __init__(self, content, stop_reason):
                        self.content = content
                        self.stop_reason = stop_reason
                        
                return OllamaResponse(content_blocks, stop_reason)
            else:
                raise Exception(f"Ollama retornó código {res.status_code}: {res.text}")
        except Exception as e:
            class ErrorResponse:
                def __init__(self, err):
                    self.stop_reason = "end_turn"
                    class ErrorBlock:
                        type = "text"
                        text = f"Error conectando a Ollama: {err}. Asegurarse de tener Ollama corriendo."
                    self.content = [ErrorBlock()]
            return ErrorResponse(e)

    def _execute_tool(self, name: str, inputs: dict) -> str:
        try:
            if name == "open_application":
                return self.system.open_app(inputs["app_name"])
            elif name == "web_search":
                return self.search.search(inputs["query"])
            elif name == "control_volume":
                return self.system.volume(inputs["action"], inputs.get("value", 50))
            elif name == "type_text":
                return self.system.type_text(inputs["text"])
            elif name == "take_screenshot":
                result = self.system.screenshot(inputs.get("filename"))
                if inputs.get("analyze"):
                    path = result.replace("Captura guardada en ", "").replace(".", "")
                    return self._analyze_image(path, "¿Qué hay en esta captura de pantalla?")
                return result
            elif name == "open_url":
                return self.system.open_url(inputs["url"])
            elif name == "run_command":
                cmd = inputs["command"]
                shell = inputs.get("shell", "cmd")
                
                # Palabras clave sospechosas o potencialmente peligrosas
                dangerous_keywords = [
                    "del", "rm", "rd", "rmdir", "format", "shutdown", "restart", 
                    "taskkill", "kill", "stop-process", "remove-item", "reg", 
                    "setx", "net", "sc", "powershell"
                ]
                
                import re
                cmd_lower = cmd.lower()
                is_dangerous = False
                for kw in dangerous_keywords:
                    if re.search(rf"\b{kw}\b", cmd_lower):
                        is_dangerous = True
                        break
                
                if is_dangerous:
                    warn_msg = f"⚠ Comando potencialmente peligroso detectado: '{cmd}'"
                    print(f"\n[JARVIS] {warn_msg}")
                    if self.hud:
                        self.hud.add_log("warn", "⚠ Comando peligroso detectado")
                        self.hud.update_status("Esperando confirmación...")
                    
                    if self.speaker:
                        # Avisar por voz de manera segura
                        msg_hablado = f"Señor, he detectado un comando potencialmente peligroso. ¿Confirma la ejecución de {cmd}?"
                        self.speaker._speak_sync(msg_hablado)
                    
                    print(f"[JARVIS] Escriba 'si' / 'confirmar' para proceder, o cualquier otra cosa para cancelar.")
                    confirm = input("¿Confirmar ejecución? (s/n): ")
                    if confirm.lower().strip() in ["s", "si", "yes", "y", "confirmar", "sí"]:
                        if self.hud:
                            self.hud.add_log("ok", "Comando confirmado")
                        return self.system.run_command(cmd, shell)
                    else:
                        if self.hud:
                            self.hud.add_log("warn", "Comando cancelado por seguridad")
                        return "Comando cancelado por el usuario por motivos de seguridad."
                else:
                    return self.system.run_command(cmd, shell)
            elif name == "get_system_info":
                return self.system.get_info(inputs["info_type"])
            elif name == "set_reminder":
                rid = self.reminders.add(
                    text=inputs["text"],
                    seconds_from_now=inputs["seconds"],
                    repeat_seconds=inputs.get("repeat_seconds")
                )
                return f"Recordatorio #{rid} creado: '{inputs['text']}' en {inputs['seconds']}s."
            elif name == "list_reminders":
                rems = self.reminders.list_all()
                if not rems:
                    return "No hay recordatorios activos."
                lines = [f"#{r['id']}: {r['text']} (en {r['remaining_seconds']}s)" for r in rems]
                return "\n".join(lines)
            elif name == "cancel_reminder":
                self.reminders.remove(inputs["reminder_id"])
                return f"Recordatorio #{inputs['reminder_id']} cancelado."
            elif name == "recall_memory":
                results = self.memory.search_similar(inputs["query"], top_k=3)
                if not results:
                    return "No encontré recuerdos relacionados."
                lines = []
                for score, ts, user, response in results:
                    if score > 0.1:
                        lines.append(f"[{ts[:10]}] {user[:80]} → {response[:80]}")
                return "\n".join(lines) if lines else "No encontré nada relevante."
            elif name == "analyze_screen":
                return self._take_and_analyze(inputs["question"])
            elif name == "media_control":
                return self.system.media_control(inputs["action"])
            elif name == "window_control":
                return self.system.window_control(inputs["action"])
            return f"Tool '{name}' no implementada."
        except Exception as e:
            return f"Error ejecutando {name}: {e}"

    def _take_and_analyze(self, question: str) -> str:
        """Toma screenshot y lo analiza con Claude Vision."""
        try:
            import os, datetime, base64
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(os.path.expanduser("~"), "Pictures", f"jarvis_vision_{ts}.png")

            try:
                import pyautogui
                img = pyautogui.screenshot()
                img.save(path)
            except Exception as e:
                return f"No pude tomar captura: {e}"

            with open(path, "rb") as f:
                img_b64 = base64.standard_b64encode(f.read()).decode()

            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=500,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": img_b64
                            }
                        },
                        {
                            "type": "text",
                            "text": f"Respondé en español rioplatense, conciso (máx 3 oraciones): {question}"
                        }
                    ]
                }]
            )
            return next((b.text for b in response.content if hasattr(b, "text")), "No pude analizar.")
        except Exception as e:
            return f"Error en análisis visual: {e}"

    def _analyze_image(self, path: str, question: str) -> str:
        try:
            import base64
            with open(path, "rb") as f:
                img_b64 = base64.standard_b64encode(f.read()).decode()
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=400,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image",
                         "source": {"type": "base64", "media_type": "image/png", "data": img_b64}},
                        {"type": "text", "text": f"Respondé en español conciso: {question}"}
                    ]
                }]
            )
            return next((b.text for b in response.content if hasattr(b, "text")), "No analizable.")
        except Exception as e:
            return f"Error visión: {e}"
