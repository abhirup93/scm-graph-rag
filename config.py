"""
Central config — loads .env and exposes typed constants.
Import this everywhere; never call os.getenv() directly in other modules.
"""
import os
from pathlib import Path
from urllib.parse import quote
from dotenv import load_dotenv

# Works whether called from src/, notebooks/, or streamlit_app/
_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env", override=True)

# ── LLM ───────────────────────────────────────────────────────────────────────
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
GROQ_MODEL   = "llama-3.3-70b-versatile"

# ── Weaviate ──────────────────────────────────────────────────────────────────
HF_API_KEY           = os.environ["HF_API_KEY"]
WEAVIATE_URL         = os.environ["WEAVIATE_URL"].rstrip("/")
WEAVIATE_API_KEY     = os.environ["WEAVIATE_API_KEY"]
COHERE_API_KEY       = os.environ.get("COHERE_API_KEY", "")
WEAVIATE_COLLECTION  = "ScmChunks"
WEAVIATE_EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
WEAVIATE_RERANKER_MODEL = "rerank-english-v3.0"

# ── Neo4j ─────────────────────────────────────────────────────────────────────
NEO4J_URI      = os.environ["NEO4J_URI"]
NEO4J_USERNAME = os.environ["NEO4J_USERNAME"]
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

# ── PostgreSQL ────────────────────────────────────────────────────────────────
PG_USER     = os.environ["PG_USER"]
PG_PASSWORD = os.environ["PG_PASSWORD"]
PG_HOST     = os.getenv("PG_HOST", "localhost")
PG_PORT     = os.getenv("PG_PORT", "5432")
PG_DATABASE = os.getenv("PG_DATABASE", "postgres")

# psycopg3 URI — URL-encodes password so special chars (e.g. @) are safe
DB_URI = (
    f"postgresql://{quote(PG_USER, safe='')}:{quote(PG_PASSWORD, safe='')}"
    f"@{PG_HOST}:{PG_PORT}/{PG_DATABASE}"
)

# psycopg2 kwargs — avoids URI encoding entirely
DB_KWARGS = dict(
    host=PG_HOST, port=int(PG_PORT),
    dbname=PG_DATABASE, user=PG_USER, password=PG_PASSWORD,
)
