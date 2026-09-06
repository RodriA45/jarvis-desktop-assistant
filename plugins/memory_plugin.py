from modules.plugin_manager import BasePlugin

class MemoryPlugin(BasePlugin):
    def get_tools(self):
        return [
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
            }
        ]

    def execute(self, tool_name: str, **kwargs) -> str:
        if tool_name == "set_reminder":
            rid = self.brain.reminders.add(
                text=kwargs["text"],
                seconds_from_now=kwargs["seconds"],
                repeat_seconds=kwargs.get("repeat_seconds")
            )
            return f"Recordatorio #{rid} creado: '{kwargs['text']}' en {kwargs['seconds']}s."
            
        elif tool_name == "list_reminders":
            rems = self.brain.reminders.list_all()
            if not rems:
                return "No hay recordatorios activos."
            lines = [f"#{r['id']}: {r['text']} (en {r['remaining_seconds']}s)" for r in rems]
            return "\n".join(lines)
            
        elif tool_name == "cancel_reminder":
            self.brain.reminders.remove(kwargs["reminder_id"])
            return f"Recordatorio #{kwargs['reminder_id']} cancelado."
            
        elif tool_name == "recall_memory":
            results = self.brain.memory.search_similar(kwargs["query"], top_k=3)
            if not results:
                return "No encontré recuerdos relacionados."
            lines = []
            for score, ts, user, response in results:
                if score > 0.1:
                    lines.append(f"[{ts[:10]}] {user[:80]} → {response[:80]}")
            return "\n".join(lines) if lines else "No encontré nada relevante."
            
        return f"Tool {tool_name} no manejada por MemoryPlugin"
