from modules.plugin_manager import BasePlugin

class WebPlugin(BasePlugin):
    def get_tools(self):
        return [
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
            }
        ]

    def execute(self, tool_name: str, **kwargs) -> str:
        if tool_name == "web_search":
            return self.brain.search.search(kwargs["query"])
        elif tool_name == "open_url":
            url = kwargs["url"]
            if url.startswith("spotify_search:"):
                q = url.replace("spotify_search:", "")
                return self.brain.system.play_spotify(q)
            return self.brain.system.open_url(url)
        elif tool_name == "take_screenshot":
            result = self.brain.system.screenshot(kwargs.get("filename"))
            if kwargs.get("analyze"):
                path = result.replace("Captura guardada en ", "").replace(".", "")
                return self._analyze_image(path, "¿Qué hay en esta captura de pantalla?")
            return result
        elif tool_name == "analyze_screen":
            return self._take_and_analyze(kwargs["question"])
            
        return f"Tool {tool_name} no manejada por WebPlugin"

    def _take_and_analyze(self, question: str) -> str:
        """Toma screenshot y lo analiza con Claude Vision."""
        try:
            import os, datetime
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(os.path.expanduser("~"), "Pictures", f"jarvis_vision_{ts}.png")

            try:
                import pyautogui
                img = pyautogui.screenshot()
                img.save(path)
            except Exception as e:
                return f"No pude tomar captura: {e}"

            return self._analyze_image(path, question)
        except Exception as e:
            return f"Error en analyze_screen: {e}"
            
    def _analyze_image(self, image_path: str, question: str) -> str:
        try:
            import base64
            from anthropic import Anthropic
            import config
            
            with open(image_path, "rb") as f:
                img_data = base64.b64encode(f.read()).decode("utf-8")

            client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
            response = client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=config.CLAUDE_MAX_TOKENS,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": img_data
                                }
                            },
                            {
                                "type": "text",
                                "text": question
                            }
                        ]
                    }
                ]
            )
            return response.content[0].text
        except Exception as e:
            return f"Error en Vision API: {e}"
