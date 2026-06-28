"""
SCM Graph RAG — FastAPI Backend
Serves WebSocket streaming + REST endpoints for the React frontend.
agent.py and tools.py are imported from the parent directory.
"""

import sys, os, json, uuid
from pathlib import Path
from contextlib import asynccontextmanager

# ── Import from project root ──────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from agent import (
    create_agent, run_agent_stream,
    GROQ_MODELS, detect_complexity,
)

# ── FastAPI ───────────────────────────────────────────────────────────────────
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psycopg2

# ── DB helpers ────────────────────────────────────────────────────────────────
PG_KWARGS = dict(
    host=os.getenv("PG_HOST", "localhost"),
    port=int(os.getenv("PG_PORT", "5432")),
    dbname=os.getenv("PG_DATABASE", "postgres"),
    user=os.getenv("PG_USER"),
    password=os.getenv("PG_PASSWORD"),
)

def get_conn():
    return psycopg2.connect(**PG_KWARGS)

def init_db():
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS scm_conversation_history (
                session_id   TEXT PRIMARY KEY,
                user_name    TEXT NOT NULL DEFAULT 'local_user',
                title        TEXT,
                created_at   TIMESTAMPTZ DEFAULT NOW(),
                updated_at   TIMESTAMPTZ DEFAULT NOW(),
                turn_count   INTEGER DEFAULT 0,
                messages     TEXT
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_scm_user
            ON scm_conversation_history(user_name)
        """)
    conn.commit()
    conn.close()

# ── Agent cache ───────────────────────────────────────────────────────────────
_agent_cache: dict = {}

def get_agent(model_id: str):
    if model_id not in _agent_cache:
        _agent_cache[model_id] = create_agent(model=model_id)
    return _agent_cache[model_id]

# ── Lifespan (replaces deprecated @app.on_event) ─────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="SCM Graph RAG API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Pydantic models ───────────────────────────────────────────────────────────
class ConversationSave(BaseModel):
    session_id:  str
    user_name:   str = "local_user"
    title:       str = "Untitled"
    turn_count:  int = 0
    messages:    list

# ── REST endpoints ────────────────────────────────────────────────────────────

@app.get("/")
def health():
    return {"status": "ok", "service": "SCM Graph RAG API"}


@app.get("/models")
def list_models():
    return {
        "models": [
            {"display": k, "id": v}
            for k, v in GROQ_MODELS.items()
        ]
    }


@app.get("/conversations/{user_name}")
def get_conversations(user_name: str = "local_user"):
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """SELECT session_id, title, created_at, updated_at, turn_count, messages
                   FROM scm_conversation_history
                   WHERE user_name = %s
                   ORDER BY updated_at DESC""",
                (user_name,)
            )
            rows = cur.fetchall()
        conn.close()
        return {
            "conversations": [
                {
                    "id":         r[0],
                    "title":      r[1] or "Untitled",
                    "created_at": r[2].isoformat() if r[2] else None,
                    "updated_at": r[3].isoformat() if r[3] else None,
                    "turn_count": r[4] or 0,
                    "messages":   json.loads(r[5]) if r[5] else [],
                }
                for r in rows
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/conversations/save")
def save_conversation(data: ConversationSave):
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO scm_conversation_history
                   (session_id, user_name, title, turn_count, messages, updated_at)
                   VALUES (%s, %s, %s, %s, %s, NOW())
                   ON CONFLICT (session_id) DO UPDATE SET
                       title      = EXCLUDED.title,
                       turn_count = EXCLUDED.turn_count,
                       messages   = EXCLUDED.messages,
                       updated_at = NOW()""",
                (data.session_id, data.user_name, data.title,
                 data.turn_count, json.dumps(data.messages))
            )
        conn.commit()
        conn.close()
        return {"status": "saved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/conversations/{session_id}")
def delete_conversation(session_id: str):
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM scm_conversation_history WHERE session_id = %s",
                (session_id,)
            )
            for tbl in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
                cur.execute(
                    f"DELETE FROM public.{tbl} WHERE thread_id = %s",
                    (session_id,)
                )
        conn.commit()
        conn.close()
        return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── WebSocket streaming endpoint ──────────────────────────────────────────────

@app.websocket("/ws/chat")
async def websocket_chat(ws: WebSocket):
    """
    Client sends:  {"query": "...", "thread_id": "...", "model": "auto"}
    Server streams: model_selected → tool_call → tool_result → token → done
    """
    await ws.accept()
    try:
        while True:
            raw  = await ws.receive_text()
            data = json.loads(raw)

            query     = data.get("query", "").strip()
            thread_id = data.get("thread_id", str(uuid.uuid4()))
            model_req = data.get("model", "auto")

            if not query:
                await ws.send_json({"type": "error", "message": "Empty query"})
                continue

            # Resolve model
            if model_req == "auto":
                model_id, label, reason = detect_complexity(query)
            else:
                model_id = model_req
                label    = "Manual"
                reason   = f"Manually selected: {model_id}"

            await ws.send_json({
                "type"     : "model_selected",
                "model"    : model_id,
                "label"    : label,
                "reason"   : reason,
                "thread_id": thread_id,
            })

            # Stream agent events
            agent = get_agent(model_id)
            try:
                for event in run_agent_stream(agent, query, thread_id):
                    await ws.send_json(event)
            except Exception as e:
                await ws.send_json({"type": "error", "message": str(e)})

            await ws.send_json({"type": "done", "thread_id": thread_id})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await ws.send_json({"type": "error", "message": str(e)})
        except:
            pass