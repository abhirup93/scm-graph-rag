# 🕸️ SCM Graph RAG — Local Build

<p align="center">
  <a href="https://github.com/abhirup93/scm-graph-rag/stargazers">
    <img src="https://img.shields.io/github/stars/abhirup93/scm-graph-rag?style=social" alt="Stars"/>
  </a>
  <a href="https://github.com/abhirup93/scm-graph-rag/network/members">
    <img src="https://img.shields.io/github/forks/abhirup93/scm-graph-rag?style=social" alt="Forks"/>
  </a>
  <a href="https://github.com/abhirup93/scm-graph-rag/watchers">
    <img src="https://img.shields.io/github/watchers/abhirup93/scm-graph-rag?style=social" alt="Watchers"/>
  </a>
  <a href="https://github.com/abhirup93/scm-graph-rag/issues">
    <img src="https://img.shields.io/github/issues/abhirup93/scm-graph-rag" alt="Issues"/>
  </a>
  <a href="https://github.com/abhirup93/scm-graph-rag/blob/main/LICENSE">
    <img src="https://img.shields.io/github/license/abhirup93/scm-graph-rag" alt="License"/>
  </a>
  <a href="https://github.com/abhirup93/scm-graph-rag/commits/main">
    <img src="https://img.shields.io/github/last-commit/abhirup93/scm-graph-rag" alt="Last Commit"/>
  </a>
  <img src="https://img.shields.io/github/languages/top/abhirup93/scm-graph-rag" alt="Top Language"/>
</p>

<p align="center">
A fully local <b>Hybrid Graph RAG</b> system for Supply Chain Management that combines <b>vector search</b> (Weaviate) with <b>knowledge graph traversal</b> (Neo4j) to answer complex SCM questions grounded in research literature.
</p>

---

## 🏗️ Architecture

```
User Query
    │
    ▼
┌─────────────────────────────────────────┐
│         LangGraph ReAct Agent           │
│              (Groq LLM)                 │
└──────────┬──────────────────┬───────────┘
           │                  │
           ▼                  ▼
  ┌─────────────────┐  ┌──────────────────┐
  │ Weaviate Cloud  │  │  Neo4j AuraDB    │
  │ Vector Search   │  │ Knowledge Graph  │
  │ + Cohere Rerank │  │  BFS Traversal   │
  └─────────────────┘  └──────────────────┘
           │                  │
           └────────┬─────────┘
                    ▼
           Synthesised Answer
                    │
                    ▼
        ┌───────────────────────┐
        │  Streamlit Chat UI    │
        │  + Thought Process    │
        └───────────────────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │  PostgreSQL 18        │
        │  Conversation Memory  │
        │  (LangGraph Saver)    │
        └───────────────────────┘
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **LLM** | Groq `llama-3.3-70b-versatile` |
| **Vector DB** | Weaviate Cloud (`text2vec-huggingface` + `reranker-cohere`) |
| **Knowledge Graph** | Neo4j AuraDB (Entity extraction via Groq) |
| **Agent Framework** | LangGraph `create_react_agent` |
| **Conversation Memory** | PostgreSQL 18 via `langgraph-checkpoint-postgres` |
| **Embeddings** | HuggingFace `sentence-transformers/all-MiniLM-L6-v2` |
| **Reranker** | Cohere `rerank-english-v3.0` |
| **Frontend** | Streamlit |
| **Env Management** | `uv` |

---

## 📁 Project Structure

```
scm-graph-rag/
├── agent.py                  # LangGraph ReAct agent + streaming
├── tools.py                  # Weaviate search + Neo4j graph search tools
├── notebooks/
│   ├── 00_setup_postgres.ipynb     # PostgreSQL setup
│   ├── 01_weaviate_setup.ipynb     # Weaviate collection + reranker
│   ├── 02_data_ingestion.ipynb     # PDF → chunks → Weaviate
│   ├── 03_neo4j_ingestion.ipynb    # Chunks → entities → Neo4j graph
│   ├── 04_agent_build.ipynb        # Agent build & test
│   └── 05_retrieval_eval.ipynb     # Hit@K, MRR@K, NDCG@K evaluation
├── streamlit_app/
│   └── app.py                # Chat UI with streaming + thought process
├── data/
│   └── pdfs/                 # Drop your PDFs here (gitignored)
├── .env.example              # Environment variables template
└── pyproject.toml            # uv dependencies
```

---

## ⚙️ Prerequisites

- Python 3.11+
- [`uv`](https://github.com/astral-sh/uv) for environment management
- PostgreSQL 18 running locally
- Accounts and API keys for:
  - [Groq](https://console.groq.com) (free)
  - [Weaviate Cloud](https://console.weaviate.cloud) (free tier)
  - [HuggingFace](https://huggingface.co/settings/tokens) (free)
  - [Cohere](https://dashboard.cohere.com/api-keys) (free tier)
  - [Neo4j AuraDB](https://console.neo4j.io) (free tier)

---

## 🚀 Setup

### 1. Clone & install dependencies

```bash
git clone https://github.com/abhirup93/scm-graph-rag.git
cd scm-graph-rag

uv init
uv venv
# Windows
.venv\Scripts\activate
# Mac/Linux
source .venv/bin/activate

uv add python-dotenv neo4j "weaviate-client>=4.9" groq langchain-groq \
       langchain-core langgraph "langgraph-checkpoint-postgres>=2.0" \
       "psycopg[binary]" psycopg2-binary pymupdf langchain-text-splitters \
       streamlit jupyter ipykernel backoff pandas
```

### 2. Configure environment

```bash
cp .env.example .env
# Fill in all values in .env
```

### 3. Add research PDFs

Drop PDF files into `data/pdfs/`. Papers used in this project:

| File | Source |
|---|---|
| `2307.03875v2.pdf` | [LLMs for SCM — arXiv](https://arxiv.org/abs/2307.03875) |
| `2504.03692v1.pdf` | [Graph Digital Twin SCM — arXiv](https://arxiv.org/abs/2504.03692) |
| `2508.21622v1.pdf` | [LLM Network Optimization — arXiv](https://arxiv.org/abs/2508.21622) |
| `supply_chain_management_tutorial.pdf` | [TutorialsPoint SCM](https://www.tutorialspoint.com/supply_chain_management/supply_chain_management_tutorial.pdf) |

---

## 📓 Run Notebooks (in order)

```bash
uv run jupyter notebook
```

| Notebook | Purpose |
|---|---|
| `00_setup_postgres.ipynb` | Create LangGraph checkpoint tables + conversation history table |
| `01_weaviate_setup.ipynb` | Create Weaviate collection with vectorizer + reranker |
| `02_data_ingestion.ipynb` | Chunk PDFs → embed → insert into Weaviate (idempotent) |
| `03_neo4j_ingestion.ipynb` | Extract entities via Groq → build Neo4j knowledge graph |
| `04_agent_build.ipynb` | Test agent: single turn, multi-turn, streaming |
| `05_retrieval_eval.ipynb` | Evaluate Hit@K, MRR@K, NDCG@K — vector vs reranked |

---

## 🖥️ Run Streamlit App

```bash
uv run streamlit run streamlit_app/app.py
```

Open **http://localhost:8501**

### Features
- 💬 Multi-turn conversation with memory (PostgreSQL)
- 💭 Live **thought process** — shows which tools fired and why
- ⚡ **Streaming** response tokens (like ChatGPT)
- 📂 Conversation history with load/delete
- 🔍 Sidebar example queries

---

## 📊 Retrieval Evaluation Results

| Metric | Vector only | Vector + Rerank |
|---|---|---|
| Hit@5 | ~0.96 | ~0.75* |
| MRR@5 | ~0.94 | ~0.72* |

*Reranking bulk eval affected by Weaviate free tier gRPC limits. Individual reranking works correctly (rerank scores: 0.983 vs 0.0008).

---

## 🔑 Environment Variables

```bash
# LLM
GROQ_API_KEY=

# Weaviate
HF_API_KEY=
WEAVIATE_URL=
WEAVIATE_API_KEY=
COHERE_API_KEY=

# Neo4j AuraDB
NEO4J_URI=
NEO4J_USERNAME=
NEO4J_PASSWORD=
NEO4J_DATABASE=neo4j

# PostgreSQL (local)
PG_USER=
PG_PASSWORD=
PG_HOST=localhost
PG_PORT=5432
PG_DATABASE=postgres
```

---

## 🧠 How It Works

1. **Ingestion**: PDFs are chunked (600 chars, 80 overlap) → embedded via HuggingFace → stored in Weaviate. Simultaneously, Groq extracts named entities and relationships from each chunk → written to Neo4j with `MERGE` (idempotent).

2. **Retrieval**: For every user query, the LangGraph agent calls **both** tools:
   - `weaviate_search` — fetches top-20 chunks by vector similarity, reranks with Cohere, returns top-4
   - `neo4j_graph_search` — extracts keywords, runs BFS traversal up to 2 hops, returns entity triples

3. **Synthesis**: Groq synthesises a final answer citing both document chunks and graph triples, streamed token by token to the UI.

4. **Memory**: Every conversation turn is checkpointed to PostgreSQL via `langgraph-checkpoint-postgres`, enabling true multi-turn memory across sessions.

---

## 👥 Contributors

<a href="https://github.com/abhirup93/scm-graph-rag/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=abhirup93/scm-graph-rag" />
</a>

---

## 📄 License

MIT