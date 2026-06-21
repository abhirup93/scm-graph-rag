import sys, os, json, uuid
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load .env before anything else
load_dotenv(Path(__file__).parent.parent / ".env")

PG_USER      = os.getenv("PG_USER")
PG_PASSWORD  = os.getenv("PG_PASSWORD")
PG_HOST      = os.getenv("PG_HOST", "localhost")
PG_PORT      = os.getenv("PG_PORT", "5432")
PG_DATABASE  = os.getenv("PG_DATABASE", "postgres")
CURRENT_USER = os.getenv("APP_USER", "local_user")

DB_KWARGS = dict(
    host=PG_HOST, port=int(PG_PORT),
    dbname=PG_DATABASE, user=PG_USER, password=PG_PASSWORD,
)

# agent.py and tools.py are in project root
sys.path.insert(0, str(Path(__file__).parent.parent))
from agent import create_agent, run_agent_stream   # streaming only now

import psycopg2
import streamlit as st

st.set_page_config(page_title="SCM Graph RAG", page_icon="🕸️", layout="wide")
st.markdown("""<style>
.block-container{padding-top:1.5rem}
</style>""", unsafe_allow_html=True)

# ── Agent (singleton) ─────────────────────────────────────────────────────────
@st.cache_resource(show_spinner="Loading SCM Graph RAG agent...")
def get_agent():
    return create_agent()

AGENT = get_agent()

# ── PostgreSQL helpers ────────────────────────────────────────────────────────
def _conn(): return psycopg2.connect(**DB_KWARGS)

@st.cache_resource
def _init_db():
    try:
        c = _conn()
        with c.cursor() as cur:
            cur.execute("""CREATE TABLE IF NOT EXISTS scm_conversation_history (
                session_id TEXT PRIMARY KEY, user_name TEXT NOT NULL, title TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW(),
                turn_count INTEGER DEFAULT 0, messages TEXT)""")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_scm_user ON scm_conversation_history(user_name)")
        c.commit(); c.close()
        return True
    except Exception as e:
        st.error(f"DB init: {e}"); return False

_db_ready = _init_db()

def db_load(user):
    if not _db_ready: return {}
    try:
        c = _conn()
        with c.cursor() as cur:
            cur.execute(
                "SELECT session_id,title,created_at,turn_count,messages "
                "FROM scm_conversation_history WHERE user_name=%s ORDER BY updated_at DESC",
                (user,)
            )
            rows = cur.fetchall()
        c.close()
        return {
            sid: {
                "id": sid, "title": title or "Untitled",
                "created_at": ca.strftime("%b %d, %H:%M") if ca else "",
                "turn_count": tc or 0,
                "messages": json.loads(msgs) if msgs else [],
            }
            for sid, title, ca, tc, msgs in rows
        }
    except Exception as e:
        st.warning(f"Load: {e}"); return {}

def db_save(conv, user):
    if not _db_ready or not conv.get("messages"): return
    try:
        c = _conn()
        with c.cursor() as cur:
            cur.execute(
                """INSERT INTO scm_conversation_history
                   (session_id,user_name,title,turn_count,messages,updated_at)
                   VALUES(%s,%s,%s,%s,%s,NOW())
                   ON CONFLICT(session_id) DO UPDATE SET
                   title=EXCLUDED.title, turn_count=EXCLUDED.turn_count,
                   messages=EXCLUDED.messages, updated_at=NOW()""",
                (conv["id"], user, conv.get("title","Untitled"),
                 conv.get("turn_count",0), json.dumps(conv.get("messages",[])))
            )
        c.commit(); c.close()
    except Exception as e:
        st.warning(f"Save: {e}")

def db_delete(sid):
    if not _db_ready: return
    try:
        c = _conn()
        with c.cursor() as cur:
            cur.execute("DELETE FROM scm_conversation_history WHERE session_id=%s", (sid,))
            for tbl in ("checkpoint_writes","checkpoint_blobs","checkpoints"):
                cur.execute(f"DELETE FROM public.{tbl} WHERE thread_id=%s", (sid,))
        c.commit(); c.close()
    except Exception as e:
        st.warning(f"Delete: {e}")

def db_delete_all(user):
    if not _db_ready: return
    try:
        c = _conn()
        with c.cursor() as cur:
            cur.execute("SELECT session_id FROM scm_conversation_history WHERE user_name=%s", (user,))
            sids = [r[0] for r in cur.fetchall()]
            cur.execute("DELETE FROM scm_conversation_history WHERE user_name=%s", (user,))
            for sid in sids:
                for tbl in ("checkpoint_writes","checkpoint_blobs","checkpoints"):
                    cur.execute(f"DELETE FROM public.{tbl} WHERE thread_id=%s", (sid,))
        c.commit(); c.close()
    except Exception as e:
        st.warning(f"Delete all: {e}")

# ── Session state ─────────────────────────────────────────────────────────────
def _init():
    for k, v in {
        "conversations": {}, "active_session_id": str(uuid.uuid4()),
        "messages": [], "turn_count": 0, "pending_query": None,
        "load_session_id": None, "db_loaded": False,
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init()
if not st.session_state["db_loaded"]:
    st.session_state["conversations"].update(db_load(CURRENT_USER))
    st.session_state["db_loaded"] = True

# ── Conversation helpers ───────────────────────────────────────────────────────
def _first_msg(msgs):
    for m in msgs:
        if m.get("role") == "user":
            t = m["content"].strip()
            return (t[:45] + "...") if len(t) > 45 else t
    return "Untitled"

def save_current():
    sid  = st.session_state["active_session_id"]
    msgs = st.session_state["messages"]
    if not msgs: return
    ex   = st.session_state["conversations"].get(sid, {})
    conv = {
        "id": sid, "title": _first_msg(msgs), "messages": list(msgs),
        "created_at": ex.get("created_at", datetime.now().strftime("%b %d, %H:%M")),
        "turn_count": st.session_state["turn_count"],
    }
    st.session_state["conversations"][sid] = conv
    db_save(conv, CURRENT_USER)

def new_session():
    save_current()
    st.session_state.update({
        "active_session_id": str(uuid.uuid4()),
        "messages": [], "turn_count": 0, "pending_query": None,
    })

def load_session(sid):
    save_current()
    conv = st.session_state["conversations"].get(sid)
    if not conv: return
    st.session_state.update({
        "active_session_id": sid,
        "messages": list(conv["messages"]),
        "turn_count": conv.get("turn_count", 0),
    })

def delete_session(sid):
    st.session_state["conversations"].pop(sid, None)
    db_delete(sid)
    if st.session_state["active_session_id"] == sid:
        new_session()

if st.session_state["load_session_id"]:
    load_session(st.session_state["load_session_id"])
    st.session_state["load_session_id"] = None

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🕸️ SCM Graph RAG")
    st.caption("Groq · Weaviate · Neo4j · LangGraph")
    st.divider()
    st.markdown("**👤 User**")
    st.caption(CURRENT_USER)
    st.markdown(
        ":green[🗄️ **PostgreSQL connected**]" if _db_ready
        else ":orange[⚠️ **DB unavailable**]"
    )
    st.divider()
    st.markdown("**Current Session**")
    st.code(st.session_state["active_session_id"][:18] + "...", language=None)
    st.caption(f"Turns: {st.session_state['turn_count']}")

    if st.button("➕ New Conversation", use_container_width=True, type="primary"):
        new_session(); st.rerun()

    st.divider()
    st.markdown("**📂 Conversation History**")
    history = {
        sid: conv for sid, conv in st.session_state["conversations"].items()
        if sid != st.session_state["active_session_id"] and conv.get("messages")
    }
    if not history:
        st.caption("No past conversations yet.")
    else:
        if st.button("🗑️ Delete All", use_container_width=True, type="secondary"):
            st.session_state.update({
                "conversations": {}, "active_session_id": str(uuid.uuid4()),
                "messages": [], "turn_count": 0,
            })
            db_delete_all(CURRENT_USER); st.rerun()
        st.markdown("---")
        for sid, conv in sorted(
            history.items(), key=lambda x: x[1].get("created_at", ""), reverse=True
        ):
            c1, c2 = st.columns([5, 1])
            with c1:
                if st.button(
                    f"💬 {conv.get('title','Untitled')}", key=f"load_{sid}",
                    use_container_width=True,
                    help=f"{conv.get('turn_count',0)} turns · {conv.get('created_at','')}",
                ):
                    st.session_state["load_session_id"] = sid; st.rerun()
            with c2:
                with st.popover("⋮"):
                    st.caption(f"{conv.get('turn_count',0)} turns")
                    if st.button("🗑️ Delete", key=f"del_{sid}", type="primary"):
                        delete_session(sid); st.rerun()

    st.divider()
    st.markdown("**💡 Try These**")
    for ex in [
        "What are the main SCM risks for electronics?",
        "Which suppliers depend on port logistics?",
        "How does JIT inventory affect supplier risk?",
        "Explain demand forecasting in supply chains.",
        "What technologies optimize supply chain planning?",
    ]:
        if st.button(ex, key=f"ex_{hash(ex)}", use_container_width=True):
            st.session_state["pending_query"] = ex
    st.divider()
    st.caption("© SCM Graph RAG · Local Build")

# ── Main chat ─────────────────────────────────────────────────────────────────
col_h, col_c = st.columns([5, 1])
with col_h:
    st.title("🕸️ Supply Chain Graph RAG")
    active_title = (
        _first_msg(st.session_state["messages"])
        if st.session_state["messages"] else "New Conversation"
    )
    st.caption(f"**{active_title}** · Neo4j + Weaviate · Groq llama-3.3-70b")
with col_c:
    st.write("")
    if st.button("🗑️ Clear"):
        sid = st.session_state["active_session_id"]
        db_delete(sid)
        st.session_state["conversations"].pop(sid, None)
        st.session_state.update({"messages": [], "turn_count": 0})
        st.rerun()

st.divider()

if not st.session_state["messages"]:
    with st.chat_message("assistant"):
        st.markdown(
            "👋 **Welcome to SCM Graph RAG!**\n\n"
            "I combine a Neo4j knowledge graph with Weaviate vector search "
            "to answer supply chain questions. Try asking:\n\n"
            "- 🕸️ *Which suppliers are exposed to port risks?*\n"
            "- 📄 *What does literature say about JIT inventory?*\n"
            "- 📊 *What are key SCM performance metrics?*"
        )

for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        # Show thought process for assistant messages if saved
        if msg["role"] == "assistant" and msg.get("thinking"):
            with st.expander("💭 Thought process", expanded=False):
                for step in msg["thinking"]:
                    st.markdown(step)
        st.markdown(msg["content"])
        if "ts" in msg:
            st.caption(msg["ts"])

user_query = (
    st.session_state.pop("pending_query", None)
    or st.chat_input("Ask about supply chain risks, suppliers, logistics...")
)

if user_query:
    ts = datetime.now().strftime("%H:%M")
    st.session_state["messages"].append({"role": "user", "content": user_query, "ts": ts})
    with st.chat_message("user"):
        st.markdown(user_query)
        st.caption(ts)

    with st.chat_message("assistant"):
        thinking_placeholder = st.empty()
        response_placeholder = st.empty()

        thinking_steps = []
        full_response  = ""

        for event in run_agent_stream(
            AGENT, user_query, st.session_state["active_session_id"]
        ):
            etype = event["type"]

            # ── Tool call: agent decided to use a tool ────────────────────────
            if etype == "tool_call":
                tool  = event["tool"]
                query = event.get("query", "")
                label = (
                    f"🔍 **Searching documents**"
                    f"{f': *{query[:60]}*' if query else '...'}"
                    if "weaviate" in tool else
                    f"🕸️ **Querying knowledge graph**"
                    f"{f': *{query[:60]}*' if query else '...'}"
                )
                thinking_steps.append(label)
                with thinking_placeholder.container():
                    with st.expander("💭 Thinking...", expanded=True):
                        for s in thinking_steps:
                            st.markdown(s)

            # ── Tool result: tool finished ────────────────────────────────────
            elif etype == "tool_result":
                tool  = event["tool"]
                label = (
                    "✅ Document search complete"
                    if "weaviate" in tool else
                    "✅ Graph traversal complete"
                )
                thinking_steps.append(label)
                with thinking_placeholder.container():
                    with st.expander("💭 Thinking...", expanded=True):
                        for s in thinking_steps:
                            st.markdown(s)

            # ── Token: streaming the final response ───────────────────────────
            elif etype == "token":
                full_response += event["content"]
                response_placeholder.markdown(full_response + "▌")

        # Finalise — remove cursor, collapse thinking expander
        response_placeholder.markdown(full_response)
        ts2 = datetime.now().strftime("%H:%M")
        st.caption(ts2)

        if thinking_steps:
            with thinking_placeholder.container():
                with st.expander("💭 Thought process", expanded=False):
                    for s in thinking_steps:
                        st.markdown(s)

    st.session_state["messages"].append({
        "role"    : "assistant",
        "content" : full_response,
        "ts"      : ts2,
        "thinking": thinking_steps,   # saved so it shows when scrolling back
    })
    st.session_state["turn_count"] += 1
    save_current()
    st.rerun()