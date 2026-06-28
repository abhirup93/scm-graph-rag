import sys, os, json, uuid, re
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

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

sys.path.insert(0, str(Path(__file__).parent.parent))
from agent import create_agent, run_agent_stream, GROQ_MODELS, detect_complexity

import psycopg2
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="SCM Graph RAG", page_icon="🕸️", layout="wide")
st.markdown("""<style>
.block-container{padding-top:1.5rem}
</style>""", unsafe_allow_html=True)


# ── Source Ontology Graph (Claude-style dark interactive) ─────────────────────

def _doc_label(filename):
    import re
    m = re.match(r"(\d{4}\.\d{5})(v\d+)\.pdf", filename)
    if m:
        return f"arXiv:{m.group(1)}"
    name = filename.replace("_", " ").replace(".pdf", "")
    return name[:22] + "…" if len(name) > 22 else name


def _score_color(score):
    if score >= 0.7: return "#bbf7d0", "#16a34a", "#14532d"
    if score >= 0.4: return "#fef08a", "#ca8a04", "#713f12"
    return "#bfdbfe", "#3b82f6", "#1e3a8a"


def render_source_graph(query: str, sources: list):
    import re
    import plotly.graph_objects as go

    if not sources:
        return

    # ── Group sources ─────────────────────────────────────────────────────────
    arxiv_groups, standalone = {}, []
    for src in sources:
        m = re.match(r"(\d{4}\.\d{5})(v\d+)\.pdf", src["file"])
        if m:
            arxiv_groups.setdefault(m.group(1), []).append({**src, "_ver": m.group(2)})
        else:
            standalone.append(src)

    # ── Node positions ────────────────────────────────────────────────────────
    pos, meta = {}, {}
    NW, NH = 0.55, 0.22   # node half-width, half-height

    # Query at x=0
    short_q = (query[:38] + "…") if len(query) > 38 else query
    pos["query"] = (0.0, 0.0)
    meta["query"] = dict(label=f"🔍 {short_q}", bg="#6366f1",
                         border="#4338ca", font="#ffffff", bold=True)

    # Level-1: arxiv parents + standalone
    l1 = [f"p_{aid}" for aid in arxiv_groups] + [s["file"] for s in standalone]
    n1 = len(l1)
    for i, nid in enumerate(l1):
        y = (i - (n1-1)/2) * 0.75
        pos[nid] = (1.5, y)
        if nid.startswith("p_"):
            aid = nid[2:]
            pos[nid] = (1.5, y)
            meta[nid] = dict(label=f"📄 arXiv:{aid}", bg="#f8fafc",
                             border="#94a3b8", font="#334155", bold=False)
        else:
            src = next(s for s in standalone if s["file"] == nid)
            bg, bd, fc = _score_color(src["max_score"])
            meta[nid] = dict(label=f"📘 {_doc_label(nid)}", bg=bg,
                             border=bd, font=fc, bold=False)

    # Level-2: versions under each arxiv paper
    for aid, versions in arxiv_groups.items():
        py = pos[f"p_{aid}"][1]
        nv = len(versions)
        for j, v in enumerate(versions):
            y = py + (j - (nv-1)/2) * 0.55
            pos[v["file"]] = (3.0, y)
            bg, bd, fc = _score_color(v["max_score"])
            meta[v["file"]] = dict(
                label=f"{v['_ver'].upper()} · {v['chunk_count']}ch · {v['avg_score']}",
                bg=bg, border=bd, font=fc, bold=False,
            )

    # ── Build edge list ───────────────────────────────────────────────────────
    edges = []
    for aid, versions in arxiv_groups.items():
        total = sum(v["chunk_count"] for v in versions)
        mx    = max(v["max_score"] for v in versions)
        edges.append(("query", f"p_{aid}", f"{total} chunk{'s' if total>1 else ''}", max(1.5, mx*3), False))
        for v in versions:
            edges.append((f"p_{aid}", v["file"], "", 1.5, True))
    for src in standalone:
        edges.append(("query", src["file"],
                      f"{src['chunk_count']} chunk{'s' if src['chunk_count']>1 else ''}",
                      max(1.5, src["max_score"]*3), False))

    # ── Draw ──────────────────────────────────────────────────────────────────
    fig = go.Figure()

    # Edges (lines)
    for src_id, dst_id, elabel, lw, dashed in edges:
        x0, y0 = pos[src_id]
        x1, y1 = pos[dst_id]
        # Offset start/end to edge of node box
        x0e = x0 + NW
        x1e = x1 - NW
        dash = "dot" if dashed else "solid"
        fig.add_trace(go.Scatter(
            x=[x0e, x1e], y=[y0, y1], mode="lines",
            line=dict(color="#cbd5e1", width=lw, dash=dash),
            hoverinfo="none", showlegend=False,
        ))
        fig.add_annotation(
            x=x1e, y=y1, ax=x0e, ay=y0,
            xref="x", yref="y", axref="x", ayref="y",
            showarrow=True, arrowhead=2, arrowsize=0.8,
            arrowwidth=max(1, lw*0.5), arrowcolor="#94a3b8",
        )
        if elabel:
            fig.add_annotation(
                x=(x0e+x1e)/2, y=(y0+y1)/2 + 0.06,
                text=elabel, showarrow=False,
                font=dict(size=9, color="#6366f1"),
                bgcolor="white", borderpad=2, opacity=0.9,
            )

    # Nodes (rect shapes + annotation labels)
    for nid, (x, y) in pos.items():
        m = meta[nid]
        fig.add_shape(
            type="rect",
            x0=x-NW, y0=y-NH, x1=x+NW, y1=y+NH,
            fillcolor=m["bg"],
            line=dict(color=m["border"], width=2),
            layer="above",
        )
        fig.add_annotation(
            x=x, y=y,
            text=f"<b>{m['label']}</b>" if m["bold"] else m["label"],
            showarrow=False,
            font=dict(size=10, color=m["font"],
                      family="Inter, system-ui, sans-serif"),
            xanchor="center", yanchor="middle",
            bgcolor="rgba(0,0,0,0)",
        )

    # Invisible legend traces
    for label, bg, bd in [
        ("Query",               "#6366f1", "#4338ca"),
        ("Paper",               "#f8fafc", "#94a3b8"),
        ("High relevance ≥0.7", "#bbf7d0", "#16a34a"),
        ("Medium ≥0.4",         "#fef08a", "#ca8a04"),
        ("Lower",               "#bfdbfe", "#3b82f6"),
    ]:
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers",
            marker=dict(size=11, color=bg,
                        line=dict(color=bd, width=2), symbol="square"),
            name=label, showlegend=True,
        ))

    # ── Layout ────────────────────────────────────────────────────────────────
    all_y = [y for _, y in pos.values()]
    y_pad = max(0.5, NH * 3)
    y_min = min(all_y) - y_pad
    y_max = max(all_y) + y_pad

    fig.update_layout(
        height=max(320, int((y_max - y_min) * 160 + 120)),
        paper_bgcolor="white", plot_bgcolor="white",
        xaxis=dict(visible=False, range=[-0.7, 3.8]),
        yaxis=dict(visible=False, range=[y_min, y_max]),
        margin=dict(l=20, r=20, t=20, b=10),
        legend=dict(
            orientation="h", yanchor="bottom", y=-0.15,
            xanchor="center", x=0.5,
            font=dict(size=10, color="#64748b"),
            bgcolor="white", bordercolor="#e2e8f0", borderwidth=1,
        ),
        hoverlabel=dict(bgcolor="white", bordercolor="#e2e8f0",
                        font=dict(size=11, family="Inter,system-ui,sans-serif")),
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})



# ── Agent (cached per model) ──────────────────────────────────────────────────

@st.cache_resource(show_spinner="Loading agent...")
def get_agent(model_id: str):
    """One cached agent per model — avoids recreating on every rerun."""
    return create_agent(model=model_id)


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
        "selected_model_display": "🤖 Auto (Smart Routing)",
        "selected_model_id": "auto",
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init()
if not st.session_state["db_loaded"]:
    st.session_state["conversations"].update(db_load(CURRENT_USER))
    st.session_state["db_loaded"] = True

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
            history.items(), key=lambda x: x[1].get("created_at",""), reverse=True
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
        if msg["role"] == "assistant":
            if msg.get("thinking"):
                with st.expander("💭 Thought process", expanded=False):
                    for s in msg["thinking"]:
                        st.markdown(s)
            if msg.get("sources"):
                with st.expander("📚 Source Ontology Graph", expanded=False):
                    render_source_graph(msg.get("query",""), msg["sources"])
        st.markdown(msg["content"])
        if "ts" in msg:
            st.caption(msg["ts"])

# ── Model selector fused with chat input ─────────────────────────────────────
# CSS: fuse the selectbox bottom border with chat input top border
st.markdown("""
<style>
/* Wrapper that holds model selector + chat input as one visual unit */
div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stSelectbox"]) {
    margin-bottom: -12px !important;
    z-index: 10;
    position: relative;
}
/* Style the selectbox to look like the top bar of the chat input */
div[data-testid="stSelectbox"] > div > div {
    background-color: #1e293b !important;
    border: 1px solid #334155 !important;
    border-bottom: none !important;
    border-radius: 12px 12px 0 0 !important;
    color: #94a3b8 !important;
    font-size: 12px !important;
    min-height: 32px !important;
    padding: 2px 10px !important;
}
div[data-testid="stSelectbox"] svg { color: #64748b !important; }
/* Chat input: remove top radius to connect with selectbox */
div[data-testid="stChatInput"] > div {
    border-radius: 0 0 12px 12px !important;
    border-top: 1px solid #1e293b !important;
}
</style>
""", unsafe_allow_html=True)

_MODEL_OPTIONS = {
    "🤖  Auto  —  Smart routing by complexity":    "auto",
    "⚡  Llama 3.3 70B  —  Most capable":          "llama-3.3-70b-versatile",
    "🚀  Llama 3.1 8B   —  Fast":                  "llama-3.1-8b-instant",
    "🦙  Llama 4 Scout  —  Multimodal":  "meta-llama/llama-4-scout-17b-16e-instruct",
    "⚖️  Llama 3.1 70B  —  Balanced":               "llama-3.1-70b-versatile",
}

_current_display = st.session_state.get(
    "selected_model_display",
    "🤖  Auto  —  Smart routing by complexity"
)
_selected_display = st.selectbox(
    label="model_selector",
    options=list(_MODEL_OPTIONS.keys()),
    index=list(_MODEL_OPTIONS.keys()).index(_current_display)
          if _current_display in _MODEL_OPTIONS else 0,
    label_visibility="collapsed",
    key="model_select_fused",
)
if _selected_display != st.session_state.get("selected_model_display"):
    st.session_state["selected_model_display"] = _selected_display
    st.session_state["selected_model_id"]      = _MODEL_OPTIONS[_selected_display]
    st.rerun()

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

    # ── Resolve model: auto-detect or use manual selection ────────────────────
    selected_id = st.session_state.get("selected_model_id", "auto")
    if selected_id == "auto":
        resolved_model, complexity_label, complexity_reason = detect_complexity(user_query)
        model_note = (
            f"🧠 **Auto-selected:** `{resolved_model}` "
            f"— **{complexity_label}** · {complexity_reason}"
        )
    else:
        resolved_model    = selected_id
        complexity_label  = "Manual"
        model_note        = f"🤖 **Model:** `{resolved_model}` (manually selected)"

    AGENT = get_agent(resolved_model)

    with st.chat_message("assistant"):
        thinking_placeholder = st.empty()
        response_placeholder = st.empty()

        # Model selection is always the first thought step
        thinking_steps = [model_note]
        full_response  = ""
        all_sources    = []

        with thinking_placeholder.container():
            with st.expander("💭 Thinking...", expanded=True):
                st.markdown(model_note)

        for event in run_agent_stream(
            AGENT, user_query, st.session_state["active_session_id"]
        ):
            etype = event["type"]

            if etype == "tool_call":
                tool  = event["tool"]
                query = event.get("query", "")
                label = (
                    f"🔍 **Searching documents**{f': *{query[:60]}*' if query else '...'}"
                    if "weaviate" in tool else
                    f"🕸️ **Querying knowledge graph**{f': *{query[:60]}*' if query else '...'}"
                )
                thinking_steps.append(label)
                with thinking_placeholder.container():
                    with st.expander("💭 Thinking...", expanded=True):
                        for s in thinking_steps: st.markdown(s)

            elif etype == "tool_result":
                tool    = event["tool"]
                sources = event.get("sources", [])
                if sources:
                    all_sources.extend(sources)
                label = (
                    f"✅ Documents retrieved — "
                    f"{', '.join(s['file'] for s in sources)}"
                    if "weaviate" in tool and sources
                    else "✅ Document search complete"
                    if "weaviate" in tool
                    else "✅ Graph traversal complete"
                )
                thinking_steps.append(label)
                with thinking_placeholder.container():
                    with st.expander("💭 Thinking...", expanded=True):
                        for s in thinking_steps: st.markdown(s)

            elif etype == "token":
                full_response += event["content"]
                response_placeholder.markdown(full_response + "▌")

        # ── Finalise ──────────────────────────────────────────────────────────
        response_placeholder.markdown(full_response)
        ts2 = datetime.now().strftime("%H:%M")
        st.caption(f"{ts2} · {resolved_model} · {complexity_label}")

        if thinking_steps:
            with thinking_placeholder.container():
                with st.expander("💭 Thought process", expanded=False):
                    for s in thinking_steps: st.markdown(s)

        if all_sources:
            with st.expander("📚 Source Ontology Graph", expanded=True):
                render_source_graph(user_query, all_sources)

    st.session_state["messages"].append({
        "role"    : "assistant",
        "content" : full_response,
        "ts"      : ts2,
        "thinking": thinking_steps,
        "sources" : all_sources,
        "query"   : user_query,
        "model"   : resolved_model,
        "complexity": complexity_label,
    })
    st.session_state["turn_count"] += 1
    save_current()
    st.rerun()