import os
import importlib.util
import inspect
import sys
from pathlib import Path

class BasePlugin:
    """Clase base para todos los plugins de J.A.R.V.I.S"""
    def __init__(self, brain=None):
        self.brain = brain
        
    def get_tools(self) -> list[dict]:
        """Debe retornar una lista de schemas de herramientas (formato Anthropic)"""
        return []
        
    def execute(self, tool_name: str, **kwargs) -> str:
        """Ejecuta una herramienta y devuelve el resultado"""
        raise NotImplementedError("Plugin debe implementar execute()")


class PluginManager:
    def __init__(self, brain):
        self.brain = brain
        self.plugins: list[BasePlugin] = []
        self.tools_schema: list[dict] = []
        self.tool_to_plugin = {}
        
        self.plugins_dir = Path(__file__).parent.parent / "plugins"
        self.plugins_dir.mkdir(exist_ok=True)
        
        # Crear __init__.py vacío para que sea un paquete
        init_file = self.plugins_dir / "__init__.py"
        if not init_file.exists():
            init_file.touch()
            
    def load_all_plugins(self):
        print("[PLUGIN_MANAGER] Buscando plugins...")
        self.plugins.clear()
        self.tools_schema.clear()
        self.tool_to_plugin.clear()
        
        # Añadir al path temporalmente
        if str(self.plugins_dir.parent) not in sys.path:
            sys.path.insert(0, str(self.plugins_dir.parent))
            
        for file in self.plugins_dir.glob("*.py"):
            if file.name.startswith("__"):
                continue
                
            module_name = f"plugins.{file.stem}"
            try:
                spec = importlib.util.spec_from_file_location(module_name, file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    # Buscar clases que hereden de BasePlugin
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if obj is not BasePlugin and issubclass(obj, BasePlugin):
                            print(f"[PLUGIN_MANAGER] Cargando: {name} de {file.name}")
                            plugin_instance = obj(brain=self.brain)
                            self.plugins.append(plugin_instance)
                            
                            for tool in plugin_instance.get_tools():
                                t_name = tool["name"]
                                self.tools_schema.append(tool)
                                self.tool_to_plugin[t_name] = plugin_instance
            except Exception as e:
                import traceback
                print(f"[PLUGIN_MANAGER] Error cargando plugin {file.name}: {e}")
                traceback.print_exc()
                
        print(f"[PLUGIN_MANAGER] Se cargaron {len(self.plugins)} plugins con {len(self.tools_schema)} herramientas.")
        
    def execute_tool(self, name: str, inputs: dict) -> str:
        if name in self.tool_to_plugin:
            try:
                return self.tool_to_plugin[name].execute(name, **inputs)
            except Exception as e:
                import traceback
                print(f"[PLUGIN_MANAGER] Error ejecutando {name}: {e}")
                traceback.print_exc()
                return f"Error interno en plugin: {e}"
        return f"Herramienta '{name}' no fue encontrada en ningún plugin cargado."
