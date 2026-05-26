"""
MemoryManager — Historial persistente + memoria semántica con SQLite.
Recuerda preferencias, nombres, rutinas y recupera contexto similar.
"""
import json
import sqlite3
import datetime
import hashlib
from pathlib import Path
from config import MEMORY_FILE, MEMORY_MAX_TURNS

MEMORY_FILE.parent.mkdir(exist_ok=True)
DB_FILE = MEMORY_FILE.parent / "semantic.db"


def _embed_simple(text: str) -> list:
    """Embedding lightweight a nivel de palabras (Word Hashing Trick) con stopword filtering."""
    import re
    # Limpieza básica y tokenización a nivel de palabras
    words = re.findall(r'\w+', text.lower())
    
    # Lista optimizada de stopwords en español
    stopwords = {
        "de", "la", "el", "en", "que", "y", "a", "los", "del", "se", "las", "un", 
        "para", "con", "no", "una", "su", "al", "lo", "como", "más", "pero", "sus", 
        "este", "o", "tu", "mi", "me", "nos", "yo", "te", "es", "son", "un", "una", 
        "unos", "unas", "ese", "esa", "esos", "esas", "este", "esta", "estos", "estas"
    }
    
    # Filtrar stopwords
    words = [w for w in words if w not in stopwords]
    
    # Vector de 128 dimensiones para reducir colisiones
    vec = [0.0] * 128
    for i, word in enumerate(words):
        # Hash determinista de la palabra usando MD5
        h = int(hashlib.md5(word.encode('utf-8')).hexdigest(), 16)
        vec[h % 128] += 1.0 / (i + 1)
        
    # Normalización L2
    norm = sum(v * v for v in vec) ** 0.5
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


def _cosine(a, b):
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)



class MemoryManager:
    def __init__(self):
        self._history = []
        self.total_tokens = 0
        self._db = None
        self._init_db()
        self._load_history()

    # ── DB semántica ────────────────────────────────────────────────────────

    def _init_db(self):
        self._db = sqlite3.connect(str(DB_FILE), check_same_thread=False)
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                ts       TEXT,
                user     TEXT,
                response TEXT,
                summary  TEXT,
                embedding TEXT
            )
        """)
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS preferences (
                key   TEXT PRIMARY KEY,
                value TEXT,
                ts    TEXT
            )
        """)
        self._db.commit()

    def save_turn(self, user: str, assistant: str):
        self._history.append({"role": "user",      "content": user})
        self._history.append({"role": "assistant",  "content": assistant})

        # tokens estimados
        self.total_tokens += len(user.split()) + len(assistant.split())

        # recortar historial en RAM
        max_msgs = MEMORY_MAX_TURNS * 2
        if len(self._history) > max_msgs:
            self._history = self._history[-max_msgs:]

        # guardar en SQLite
        emb = _embed_simple(user + " " + assistant)
        ts = datetime.datetime.now().isoformat()
        summary = (user[:80] + "…") if len(user) > 80 else user
        self._db.execute(
            "INSERT INTO memories (ts, user, response, summary, embedding) VALUES (?,?,?,?,?)",
            (ts, user, assistant, summary, json.dumps(emb))
        )
        self._db.commit()

        # detectar y guardar preferencias
        self._detect_preferences(user, assistant)
        self._persist_history()

    def search_similar(self, query: str, top_k: int = 3) -> list:
        """Busca recuerdos semánticamente similares a la query."""
        qemb = _embed_simple(query)
        rows = self._db.execute(
            "SELECT ts, user, response, summary, embedding FROM memories ORDER BY id DESC LIMIT 200"
        ).fetchall()

        scored = []
        for ts, user, response, summary, emb_json in rows:
            try:
                emb = json.loads(emb_json)
                score = _cosine(qemb, emb)
                scored.append((score, ts, user, response))
            except Exception:
                pass

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:top_k]

    def get_context_for(self, query: str) -> str:
        """Devuelve contexto relevante como string para inyectar en el prompt."""
        similar = self.search_similar(query, top_k=3)
        if not similar:
            return ""
        lines = []
        for score, ts, user, response in similar:
            if score > 0.15:
                date = ts[:10] if ts else "?"
                lines.append(f"[{date}] Usuario dijo: {user[:100]} → Jarvis respondió: {response[:100]}")
        return "\n".join(lines) if lines else ""

    def _detect_preferences(self, user: str, assistant: str):
        """Extrae preferencias simples del texto y las persiste."""
        import re
        prefs = {}
        # nombre del usuario
        m = re.search(r"(?:me llamo|soy|mi nombre es)\s+([A-ZÁÉÍÓÚa-záéíóú]+)", user, re.I)
        if m:
            prefs["nombre_usuario"] = m.group(1).capitalize()
        # apps favoritas
        apps = ["spotify", "chrome", "vscode", "discord", "steam"]
        for app in apps:
            if app in user.lower():
                prefs[f"usa_{app}"] = "true"

        ts = datetime.datetime.now().isoformat()
        for k, v in prefs.items():
            self._db.execute(
                "INSERT OR REPLACE INTO preferences (key, value, ts) VALUES (?,?,?)",
                (k, v, ts)
            )
        if prefs:
            self._db.commit()

    def get_preferences(self) -> dict:
        rows = self._db.execute("SELECT key, value FROM preferences").fetchall()
        return {k: v for k, v in rows}

    def get_user_name(self) -> str:
        row = self._db.execute(
            "SELECT value FROM preferences WHERE key='nombre_usuario'"
        ).fetchone()
        return row[0] if row else None

    # ── Historial de conversación ───────────────────────────────────────────

    def get_history(self):
        return list(self._history)

    def clear(self):
        self._history = []
        self.total_tokens = 0
        self._persist_history()

    def clear_all(self):
        self.clear()
        self._db.execute("DELETE FROM memories")
        self._db.execute("DELETE FROM preferences")
        self._db.commit()

    def _load_history(self):
        if MEMORY_FILE.exists():
            try:
                data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
                self._history = data.get("history", [])
                self.total_tokens = data.get("total_tokens", 0)
            except Exception:
                self._history = []

    def _persist_history(self):
        try:
            data = {"history": self._history, "total_tokens": self.total_tokens}
            MEMORY_FILE.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            print(f"[MEMORY] Error guardando: {e}")
