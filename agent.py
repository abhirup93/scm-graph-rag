import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL   = "llama-3.3-70b-versatile"

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

import psycopg
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.postgres import PostgresSaver
from tools import weaviate_search, neo4j_graph_search

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


def create_agent():
    llm          = ChatGroq(model=GROQ_MODEL, api_key=GROQ_API_KEY, temperature=0)
    pg_conn      = psycopg.connect(DB_URI, autocommit=True)
    checkpointer = PostgresSaver(pg_conn)
    return create_react_agent(
        model=llm,
        tools=[weaviate_search, neo4j_graph_search],
        checkpointer=checkpointer,
        prompt=SYSTEM_PROMPT,
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
    Streaming mode — yields structured events for UI display.

    Event types:
      {"type": "tool_call",   "tool": "weaviate_search",    "query": "..."}
      {"type": "tool_result", "tool": "weaviate_search"}
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
            # Agent is deciding to call a tool
            if hasattr(chunk, "tool_calls") and chunk.tool_calls:
                for tc in chunk.tool_calls:
                    yield {
                        "type" : "tool_call",
                        "tool" : tc["name"],
                        "query": tc.get("args", {}).get("query", ""),
                    }
            # Agent is streaming its final response
            elif getattr(chunk, "content", ""):
                yield {"type": "token", "content": chunk.content}

        elif node == "tools":
            # Tool has finished executing
            yield {
                "type": "tool_result",
                "tool": getattr(chunk, "name", "tool"),
            }