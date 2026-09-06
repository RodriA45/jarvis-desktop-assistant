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
from modules.offline_nlp import OfflineNLPController

class LLMBlock:
    def __init__(self, type_val, **kwargs):
        self.type = type_val
        for k, v in kwargs.items():
            setattr(self, k, v)

class LLMResponse:
    def __init__(self, content, stop_reason):
        self.content = content
        self.stop_reason = stop_reason

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

from modules.plugin_manager import PluginManager
class Brain:
    def __init__(self, hud=None, speaker=None):
        self.system = SystemController()
        self.search = WebSearch()
        self.memory = MemoryManager()
        self.hud = hud
        
        self.offline_nlp = OfflineNLPController(hud=self.hud)
        self.speaker = speaker  # para recordatorios por voz
        
        # Sistema de plugins (modulares)
        self.plugin_manager = PluginManager(self)
        self.plugin_manager.load_all_plugins()

        # Sistema de recordatorios
        self.reminders = ReminderSystem(
            on_remind=self._on_reminder_fire,
            on_update=self._on_reminders_update
        )

        # Escuchar cambios de configuración desde el HUD (ej. API Key)
        if self.hud:
            self.hud.on_settings_change(self._on_settings_change)

    def _on_reminders_update(self, rems: list):
        if self.hud:
            self.hud.update_reminders(rems)

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
        if "hud_theme" in settings:
            config.HUD_THEME = settings["hud_theme"]
            print(f"[BRAIN] Tema de color cambiado a: {config.HUD_THEME}")

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

        # Limpiar wake word del inicio si está presente para no confundir al LLM/intents
        import re
        clean_input = user_input.strip()
        clean_lower = clean_input.lower()
        # Remueve signos de puntuación iniciales
        clean_lower = re.sub(r'^[¿?¡!\s,.-]+', '', clean_lower)
        for pattern in ["ey jarvis", "oye jarvis", "hola jarvis", "jarvis"]:
            if clean_lower.startswith(pattern):
                # Extraer la parte después del patrón en el original
                start_idx = clean_input.lower().index(pattern) + len(pattern)
                clean_input = clean_input[start_idx:].strip()
                # Quitar puntuación inicial de nuevo
                clean_input = re.sub(r'^[¿?¡!\s,.-]+', '', clean_input)
                break
        
        if not clean_input.strip():
            clean_input = user_input  # si quedó vacío, conservar original
            
        # Usamos el input limpio a partir de ahora
        user_input_cleaned = clean_input

        # contexto semántico
        semantic_ctx = self.memory.get_context_for(user_input_cleaned)
        prefs = self.memory.get_preferences()
        user_name = prefs.get("nombre_usuario", "señor")

        # detectar recordatorios en lenguaje natural
        if any(kw in user_input_cleaned.lower() for kw in
               ["recordame", "avisame", "recordatorio", "alarma", "cada hora"]):
            parsed = parse_reminder_from_text(user_input_cleaned)
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

        history.append({"role": "user", "content": user_input_cleaned})

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
        
        with client.messages.stream(
            model=CLAUDE_MODEL,
            max_tokens=CLAUDE_MAX_TOKENS,
            system=system_prompt or JARVIS_PERSONA,
            tools=self.plugin_manager.tools_schema,
            messages=trimmed
        ) as stream:
            sentence_buffer = ""
            full_text = ""
            
            for text_chunk in stream.text_stream:
                if text_chunk:
                    sentence_buffer += text_chunk
                    full_text += text_chunk
                    
                    if self.hud:
                        # Actualiza la UI en tiempo real
                        self.hud._js(f"window.jarvis && jarvis.setStatus({json.dumps(full_text)})")
                        
                    # Procesar oraciones completas
                    if any(sentence_buffer.endswith(p) for p in [". ", "? ", "! ", ".\n", "\n"]):
                        if len(sentence_buffer.strip()) > 5:
                            if self.speaker:
                                self.speaker.speak_now(sentence_buffer.strip())
                            sentence_buffer = ""
                            
            if sentence_buffer.strip() and self.speaker:
                self.speaker.speak_now(sentence_buffer.strip())
                
            msg = stream.get_final_message()
            
            content_blocks = []
            for block in msg.content:
                if block.type == "text":
                    content_blocks.append(LLMBlock("text", text=block.text))
                elif block.type == "tool_use":
                    content_blocks.append(LLMBlock("tool_use", id=block.id, name=block.name, input=block.input))
                    
            return LLMResponse(content_blocks, msg.stop_reason)

    def _call_offline(self, history, system_prompt=None):
        return self.offline_nlp.process_offline(history, LLMBlock, LLMResponse)

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
        for t in self.plugin_manager.tools_schema:
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
                content_blocks = []
                parts = candidate.get("content", {}).get("parts", [])
                stop_reason = "end_turn"
                text_content = ""
                for p in parts:
                     if "text" in p:
                         text_content += p["text"]
                         content_blocks.append(LLMBlock("text", text=p["text"]))
                     if "functionCall" in p:
                         fc = p["functionCall"]
                         stop_reason = "tool_use"
                         content_blocks.append(LLMBlock(
                             "tool_use",
                             id=fc.get("name"),
                             name=fc.get("name"),
                             input=fc.get("args", {})
                         ))
                         
                if text_content and self.speaker:
                    self.speaker.speak_now(text_content)
                return LLMResponse(content_blocks, stop_reason)
            else:
                raise Exception(f"Gemini API returned code {res.status_code}: {res.text}")
        except Exception as e:
            return LLMResponse([LLMBlock("text", text=f"Error conectando a Gemini: {e}. Asegúrate de tener una API key de Gemini válida.")], "end_turn")


    def _call_ollama(self, history, system_prompt=None):
        import requests
        import json
        import config
        
        # Mapear herramientas de Anthropic (TOOLS) al formato de herramientas de OpenAI/Ollama
        ollama_tools = []
        for t in self.plugin_manager.tools_schema:
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
                content_blocks = []
                if text_content:
                    content_blocks.append(LLMBlock("text", text=text_content))
                    
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
                        content_blocks.append(LLMBlock(
                            "tool_use",
                            id=tc.get("id", "tool_call_id"),
                            name=fn.get("name", ""),
                            input=args
                        ))
                        
                if text_content and self.speaker:
                    self.speaker.speak_now(text_content)
                return LLMResponse(content_blocks, stop_reason)
            else:
                raise Exception(f"Ollama retornó código {res.status_code}: {res.text}")
        except Exception as e:
            return LLMResponse([LLMBlock("text", text=f"Error conectando a Ollama: {e}. Asegurarse de tener Ollama corriendo.")], "end_turn")

    def _execute_tool(self, name: str, inputs: dict) -> str:
        return self.plugin_manager.execute_tool(name, inputs)

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
