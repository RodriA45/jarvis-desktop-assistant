"""
WebSearch — Búsqueda web usando DuckDuckGo (sin API key requerida).
"""
try:
    from duckduckgo_search import DDGS
    DDGS_OK = True
except ImportError:
    DDGS_OK = False


class WebSearch:
    def search(self, query: str, max_results: int = 4) -> str:
        if not DDGS_OK:
            return "duckduckgo-search no instalado. Ejecutá: pip install duckduckgo-search"
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, region="ar-es", max_results=max_results))
            if not results:
                return f"No encontré resultados para: {query}"
            lines = []
            for r in results:
                title = r.get("title", "")
                body = r.get("body", "")[:200]
                lines.append(f"- {title}: {body}")
            return "\n".join(lines)
        except Exception as e:
            return f"Error en búsqueda: {e}"
