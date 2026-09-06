from modules.plugin_manager import BasePlugin

class SystemPlugin(BasePlugin):
    def get_tools(self):
        return [
            {
                "name": "open_application",
                "description": "Abre una aplicación instalada en Windows",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "app_name": {"type": "string", "description": "Nombre de la app: chrome, firefox, notepad, spotify, vscode, explorer, terminal, calc, paint, word, excel, powerpoint, outlook, teams, discord, steam, vlc"}
                    },
                    "required": ["app_name"]
                }
            },
            {
                "name": "control_volume",
                "description": "Controla el volumen del sistema",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["up", "down", "mute", "unmute", "set"]},
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
                        "info_type": {"type": "string", "enum": ["all", "cpu", "ram", "disk", "battery", "network", "processes"]}
                    },
                    "required": ["info_type"]
                }
            },
            {
                "name": "media_control",
                "description": "Controla la reproducción de música de fondo (reproductores activos como Spotify)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["play_pause", "next", "prev"]}
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
                        "action": {"type": "string", "enum": ["minimize_all", "close_active", "maximize_active", "split_left", "split_right"]}
                    },
                    "required": ["action"]
                }
            },
            {
                "name": "show_widget",
                "description": "Muestra un widget HTML interactivo en la interfaz HUD de J.A.R.V.I.S.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "html_content": {"type": "string", "description": "Código HTML y CSS del widget a mostrar. Usa estilos inline o etiquetas <style> coherentes con el tema oscuro/neón."}
                    },
                    "required": ["html_content"]
                }
            }
        ]

    def execute(self, tool_name: str, **kwargs) -> str:
        sys_ctrl = self.brain.system
        
        if tool_name == "open_application":
            return sys_ctrl.open_app(kwargs["app_name"])
        elif tool_name == "control_volume":
            return sys_ctrl.volume(kwargs["action"], kwargs.get("value", 50))
        elif tool_name == "type_text":
            return sys_ctrl.type_text(kwargs["text"])
        elif tool_name == "run_command":
            cmd = kwargs["command"]
            if cmd in ["lock", "suspend", "restart", "shutdown"]:
                if cmd == "lock": return sys_ctrl.lock_screen()
                elif cmd == "suspend": return sys_ctrl.suspend_pc()
                elif cmd == "restart": return sys_ctrl.restart_pc()
                elif cmd == "shutdown": return sys_ctrl.shutdown_pc()
            
            shell = kwargs.get("shell", "cmd")
            if sys_ctrl.is_dangerous_command(cmd):
                print(f"\n[JARVIS] ⚠ Comando potencialmente peligroso detectado: '{cmd}'")
                if self.brain.hud:
                    self.brain.hud.add_log("warn", "⚠ Comando peligroso detectado")
                    self.brain.hud.update_status("Esperando confirmación...")
                if self.brain.speaker:
                    self.brain.speaker._speak_sync(f"Señor, he detectado un comando potencialmente peligroso. ¿Confirma la ejecución de {cmd}?")
                
                confirm = input("¿Confirmar ejecución? (s/n): ")
                if confirm.lower().strip() in ["s", "si", "yes", "y", "confirmar", "sí"]:
                    if self.brain.hud: self.brain.hud.add_log("ok", "Comando confirmado")
                    return sys_ctrl.run_command(cmd, shell)
                else:
                    if self.brain.hud: self.brain.hud.add_log("warn", "Comando cancelado por seguridad")
                    return "Comando cancelado por el usuario por motivos de seguridad."
            else:
                return sys_ctrl.run_command(cmd, shell)
                
        elif tool_name == "get_system_info":
            return sys_ctrl.get_info(kwargs["info_type"])
        elif tool_name == "media_control":
            return sys_ctrl.media_control(kwargs["action"])
        elif tool_name == "window_control":
            return sys_ctrl.window_control(kwargs["action"])
        elif tool_name == "show_widget":
            if self.brain.hud:
                self.brain.hud.render_widget(kwargs["html_content"])
                return "Widget renderizado correctamente en el HUD."
            return "El HUD no está activo."
            
        return f"Tool {tool_name} no manejada por SystemPlugin"
