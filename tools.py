import os
import json
import math
import re
from dotenv import load_dotenv

load_dotenv()

HF_API_KEY          = os.getenv("HF_API_KEY")
COHERE_API_KEY      = os.getenv("COHERE_API_KEY", "")
WEAVIATE_URL        = os.getenv("WEAVIATE_URL", "").rstrip("/")
WEAVIATE_API_KEY    = os.getenv("WEAVIATE_API_KEY")
WEAVIATE_COLLECTION = "ScmChunks"

NEO4J_URI      = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

import weaviate
from weaviate.classes.init import Auth
from weaviate.classes.query import Rerank
from neo4j import GraphDatabase
from langchain_core.tools import tool


def _wv_client():
    headers = {"X-HuggingFace-Api-Key": HF_API_KEY}
    if COHERE_API_KEY:
        headers["X-Cohere-Api-Key"] = COHERE_API_KEY
    return weaviate.connect_to_weaviate_cloud(
        cluster_url=WEAVIATE_URL,
        auth_credentials=Auth.api_key(WEAVIATE_API_KEY),
        headers=headers,
    )


@tool
def weaviate_search(query: str) -> str:
    """
    Semantic search over supply chain documents.
    Fetches top-20 by vector similarity then reranks with Cohere; returns top-4.
    Use for: detailed explanations, evidence, statistics, policy context.
    """
    client = _wv_client()
    try:
        collection = client.collections.get(WEAVIATE_COLLECTION)
        response = collection.query.near_text(
            query=query,
            limit=20,
            rerank=Rerank(prop="text", query=query),
            return_properties=["source_file", "chunk_idx", "text"],
        )
        objects = response.objects[:4]
        if not objects:
            return "No relevant documents found."
        parts = []
        for i, obj in enumerate(objects, 1):
            p     = obj.properties
            score = (f"{obj.metadata.rerank_score:.4f}"
                     if obj.metadata and obj.metadata.rerank_score is not None else "n/a")
            parts.append(
                f"[{i}] {p.get('source_file','?')} chunk#{p.get('chunk_idx','?')} "
                f"rerank_score={score}\n{p.get('text','').strip()}"
            )
        return "\n\n---\n\n".join(parts)
    finally:
        client.close()


_STOP = {
    "what","is","are","the","a","an","of","in","for","to","and","or",
    "how","does","do","which","where","when","who","tell","me","about","explain",
}


@tool
def neo4j_graph_search(query: str, hops: int = 2) -> str:
    """
    BFS traversal of the Neo4j supply chain knowledge graph.
    Use for: supplier relationships, risk dependencies, entity connections.
    Returns triples: EntityA --[RELATION]--> EntityB.
    """
    hop_count = max(1, min(int(hops), 3))
    entities  = [w for w in re.findall(r"\b[A-Za-z][\w\-]*\b", query)
                 if w.lower() not in _STOP and len(w) > 3][:5] or query.split()[:3]
    triples   = []

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
    try:
        with driver.session(database=NEO4J_DATABASE) as s:
            for entity in entities:
                for rec in s.run(
                    f"""MATCH (a:Entity)-[*1..{hop_count}]->(b:Entity)
                        WHERE toLower(a.name) CONTAINS toLower($nm)
                        MATCH (a)-[r]->(b)
                        RETURN a.name AS src, type(r) AS rel, b.name AS tgt LIMIT 20""",
                    nm=entity,
                ):
                    t = f"{rec['src']} --[{rec['rel']}]--> {rec['tgt']}"
                    if t not in triples:
                        triples.append(t)
    finally:
        driver.close()

    if not triples:
        return f"No graph relationships found for: {query}"
    return json.dumps({"query_entities": entities, "triples": triples, "count": len(triples)}, indent=2)


# ── Retrieval evaluation helpers ──────────────────────────────────────────────

def _dcg(rels):
    return sum(r / math.log2(i + 1) for i, r in enumerate(rels, 1))

def _ndcg(retrieved_ids, relevant_id, k):
    rels = [1.0 if rid == relevant_id else 0.0 for rid in retrieved_ids[:k]]
    dcg  = _dcg(rels)
    ideal = _dcg([1.0] + [0.0] * (k - 1))
    return dcg / ideal if ideal > 0 else 0.0

def _metrics(retrieved_ids, relevant_id, k):
    top_k = retrieved_ids[:k]
    hit   = float(relevant_id in top_k)
    rr    = next((1.0 / (i + 1) for i, rid in enumerate(top_k) if rid == relevant_id), 0.0)
    return {"hit": hit, "rr": rr, "ndcg": _ndcg(retrieved_ids, relevant_id, k)}

def eval_retrieval(sample_chunks, k=5, use_rerank=False, fetch_limit=20):
    hits, rrs, ndcgs = [], [], []
    client     = _wv_client()
    collection = client.collections.get(WEAVIATE_COLLECTION)

    try:
        for i, chunk in enumerate(sample_chunks):

            # Reconnect every 10 queries — prevents gRPC connection drop
            if i > 0 and i % 10 == 0:
                client.close()
                client     = _wv_client()
                collection = client.collections.get(WEAVIATE_COLLECTION)

            query_text  = chunk["text"][:250]
            relevant_id = chunk["chunk_id"]
            try:
                response = collection.query.near_text(
                    query=query_text,
                    limit=fetch_limit if use_rerank else k,
                    rerank=Rerank(prop="text", query=query_text) if use_rerank else None,
                    return_properties=["chunk_id"],
                )
                ids = [o.properties.get("chunk_id", "") for o in response.objects]
            except Exception as e:
                print(f"  warn: skipping chunk {i} — {type(e).__name__}")
                ids = []

            # Small delay for reranking to avoid Cohere rate limits
            if use_rerank:
                import time; time.sleep(0.5)

            m = _metrics(ids, relevant_id, k)
            hits.append(m["hit"]); rrs.append(m["rr"]); ndcgs.append(m["ndcg"])
    finally:
        client.close()

    n = len(sample_chunks)
    return {f"Hit@{k}": round(sum(hits)/n, 4), f"MRR@{k}": round(sum(rrs)/n, 4),
            f"NDCG@{k}": round(sum(ndcgs)/n, 4), "n_queries": n}