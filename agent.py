import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

PG_USER     = os.getenv("PG_USER")
PG_PASSWORD = os.getenv("PG_PASSWORD")
PG_HOST     = os.getenv("PG_HOST", "localhost")
PG_PORT     = os.getenv("PG_PORT", "5432")
PG_DATABASE = os.getenv("PG_DATABASE", "postgres")

from urllib.parse import quote
DB_URI = (
    f"postgresql://{quote(PG_USER, safe='')}:{quote(PG_PASSWORD, safe='')}"
    f"@{PG_HOST}:{PG_PORT}/{PG_DATABASE}"
)

# ── Available models ──────────────────────────────────────────────────────────
GROQ_MODELS = {
    "🤖 Auto (Smart Routing)": "auto",
    "Llama 3.3 70B — Most Capable": "llama-3.3-70b-versatile",
    "Llama 3.1 8B — Fast":          "llama-3.1-8b-instant",
    "Llama 4 Scout — Multimodal":    "meta-llama/llama-4-scout-17b-16e-instruct",
    "Llama 3.1 70B — Balanced":      "llama-3.1-70b-versatile",
}

DEFAULT_MODEL = "llama-3.3-70b-versatile"

import psycopg
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.postgres import PostgresSaver
from tools import weaviate_search, neo4j_graph_search, get_last_weaviate_sources

SYSTEM_PROMPT = (
    "You are an expert Supply Chain Management (SCM) advisor with two tools:\n\n"
    "1. weaviate_search — semantic search over SCM research papers.\n"
    "   Use for: explanations, evidence, statistics, policy context.\n\n"
    "2. neo4j_graph_search — BFS traversal of the Neo4j SCM knowledge graph.\n"
    "   Use for: supplier dependencies, risk chains, entity relationships.\n\n"
    "For EVERY query call BOTH tools, then synthesize a comprehensive answer.\n"
    "Cite graph triples: e.g. 'Graph: SupplierX --[SHIPS_TO]--> PortY'\n"
    "Cite documents: 'According to [paper], ...'\n"
    "Reference prior conversation context when relevant."
)


def create_agent(model: str = DEFAULT_MODEL):
    """Create a LangGraph ReAct agent with the specified Groq model."""
    llm          = ChatGroq(model=model, api_key=GROQ_API_KEY, temperature=0)
    pg_conn      = psycopg.connect(DB_URI, autocommit=True)
    checkpointer = PostgresSaver(pg_conn)
    return create_react_agent(
        model=llm,
        tools=[weaviate_search, neo4j_graph_search],
        checkpointer=checkpointer,
        prompt=SYSTEM_PROMPT,
    )


# ── Complexity detection ──────────────────────────────────────────────────────

_COMPLEX_SIGNALS = {
    "propagate", "cascade", "multi-tier", "multi-hop", "downstream",
    "upstream", "interconnect", "dependencies", "ripple", "amplif",
    "compare", "contrast", "versus", "trade-off", "implications",
    "mitigat", "optimiz", "strateg", "framework", "architect",
    "why does", "what causes", "how would", "what if",
}

_SIMPLE_SIGNALS = {
    "what is", "what are", "define", "definition", "list", "name",
    "who is", "where is", "when did", "give me", "tell me",
}

_MEDIUM_SIGNALS = {
    "how does", "how do", "explain", "describe", "what role",
    "what impact", "how is", "how are",
}


def detect_complexity(query: str) -> tuple[str, str, str]:
    """
    Heuristic complexity classifier.

    Returns:
        (model_id, complexity_label, reason)
    """
    q     = query.lower()
    words = q.split()
    wc    = len(words)

    complex_hits = sum(1 for s in _COMPLEX_SIGNALS if s in q)
    simple_hits  = sum(1 for s in _SIMPLE_SIGNALS  if s in q)
    medium_hits  = sum(1 for s in _MEDIUM_SIGNALS  if s in q)

    # ── Decision logic ────────────────────────────────────────────────────────
    if wc < 8 or (simple_hits >= 1 and complex_hits == 0 and wc < 15):
        return (
            "llama-3.1-8b-instant",
            "Simple",
            f"Short query ({wc} words), basic lookup pattern",
        )

    if complex_hits >= 2 or wc > 22:
        return (
            "llama-3.3-70b-versatile",
            "Complex",
            f"Multi-hop signals ({complex_hits}) detected, {wc} words",
        )

    if medium_hits >= 1 or (10 <= wc <= 22):
        return (
            "llama-3.1-70b-versatile",
            "Medium",
            f"Single-domain analytical question, {wc} words",
        )

    # Default
    return (
        "meta-llama/llama-4-scout-17b-16e-instruct",
        "Complex",
        "Defaulting to most capable model",
    )


def run_agent(agent, query: str, thread_id: str) -> str:
    """Batch mode — waits for full response."""
    config = {"configurable": {"thread_id": thread_id}}
    result = agent.invoke(
        {"messages": [{"role": "user", "content": query}]},
        config=config,
    )
    return result["messages"][-1].content


def run_agent_stream(agent, query: str, thread_id: str):
    """
    Streaming mode — yields structured events.

    Event types:
      {"type": "tool_call",   "tool": "...", "query": "..."}
      {"type": "tool_result", "tool": "...", "sources": [...]}
      {"type": "token",       "content": "..."}
    """
    config = {"configurable": {"thread_id": thread_id}}

    for chunk, metadata in agent.stream(
        {"messages": [{"role": "user", "content": query}]},
        config=config,
        stream_mode="messages",
    ):
        node = metadata.get("langgraph_node", "")

        if node == "agent":
            if hasattr(chunk, "tool_calls") and chunk.tool_calls:
                for tc in chunk.tool_calls:
                    yield {
                        "type" : "tool_call",
                        "tool" : tc["name"],
                        "query": tc.get("args", {}).get("query", ""),
                    }
            elif getattr(chunk, "content", ""):
                yield {"type": "token", "content": chunk.content}

        elif node == "tools":
            tool_name = getattr(chunk, "name", "tool")
            event = {"type": "tool_result", "tool": tool_name}
            if tool_name == "weaviate_search":
                event["sources"] = get_last_weaviate_sources()
            yield event