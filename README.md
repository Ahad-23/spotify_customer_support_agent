# SpotifyCares AI Support Platform

A Case-Based Reasoning (CBR) customer support system with real-time Human-in-the-Loop (HITL) handoff. Powered by **LangGraph**, **Elasticsearch Serverless** hybrid search, **FastAPI + WebSockets**, and **React 19**.

---

## System Architecture

```mermaid
flowchart TD
    subgraph Clients["Frontend (React 19 + Vite)"]
        CC["Customer Chat (/)\n• Streaming messages\n• Wait queue state"]
        AC["Agent Console (/agent)\n• Live ticket queue\n• One-click takeover"]
    end

    subgraph API["Backend (FastAPI + SQLite)"]
        REST["REST Endpoints\n/api/sessions, /api/agent"]
        WS["WebSocket Manager\n/ws/chat/{id}, /ws/agent"]
        DB[(SQLite / support.db\nSessions, Messages, Tickets)]
    end

    subgraph Core["Agent Core (LangGraph)"]
        IA["Intent & Sentiment Analyzer\n• Device detection\n• Frustration scoring (LiteLLM)"]
        CR["Case Retriever (CBR)\n• Hybrid Search (BM25 + Dense kNN)\n• .jina-embeddings-v5-text-nano"]
        SG["Solution Generator\n• Groq / Gemini / OpenAI\n• Deterministic Fallback"]
        HITL["HITL Escalation Node\n• Structured Ticket Dispatch\n• SPOTIFY-T2-#####"]
    end

    CC <-->|REST & WS| API
    AC <-->|REST & WS| API
    API <--> Core
    API --- DB

    IA -->|Billing / Account Security| HITL
    IA -->|Frustration >= 0.5 / Agent Request| HITL
    IA -->|Standard Troubleshooting| CR
    CR -->|Relevance < 20.0| HITL
    CR -->|Relevance >= 20.0| SG
    HITL -.->|Real-time alert| AC
```

---

## Tech Stack

| Layer | Technologies |
|---|---|
| **Frontend** | React 19, TypeScript, Vite, Tailwind CSS v4, Marked, DOMPurify |
| **Backend** | FastAPI, Uvicorn, SQLAlchemy, SQLite, WebSockets, Pydantic v2 |
| **Agent & Inference** | LangGraph, LiteLLM (Groq `gpt-oss-120b`, Gemini `gemini-3.8-flash`, OpenAI `gpt-4o-mini`) |
| **Search & Retrieval** | Elasticsearch Cloud Serverless, BM25 + Dense kNN (768d `.jina-embeddings-v5-text-nano`) |
| **Data & Tooling** | `uv`, Polars, PyArrow, Rich, Pytest |

---

## Project Structure

```
customer_support_agent/
├── backend/                  # FastAPI service & persistence layer
│   ├── database.py           # SQLite engine & session factory
│   ├── models.py             # SQLAlchemy models (ChatSession, ChatMessage, HitlTicket)
│   ├── schemas.py            # Pydantic request/response schemas
│   ├── routers/
│   │   ├── sessions.py       # Customer chat session endpoints
│   │   ├── agents.py         # Agent console ticket & message endpoints
│   │   └── ws.py             # WebSocket routes (/ws/chat, /ws/agent)
│   ├── services/
│   │   ├── chat_service.py   # Agent execution wrapper & session state sync
│   │   └── websocket_manager.py # Real-time pub/sub connection manager
│   └── main.py               # FastAPI entrypoint & static mount
├── frontend/                 # React 19 SPA (Spotify dark theme)
│   ├── src/
│   │   ├── pages/
│   │   │   ├── CustomerChat.tsx   # Customer conversational interface
│   │   │   └── AgentDashboard.tsx # HITL agent queue & live chat takeover
│   │   ├── components/       # MessageBubble, TicketCard, ChatInput, MarkdownContent
│   │   ├── hooks/            # useWebSocket hook
│   │   └── api/client.ts     # Typed fetch client
│   ├── vite.config.ts        # Vite dev server with /api and /ws proxy
│   └── package.json
├── src/                      # Core agent & RAG pipeline
│   ├── agent/
│   │   ├── graph.py          # LangGraph StateGraph & conditional edge routing
│   │   ├── nodes.py          # Analyzer, retriever, generator, escalation nodes
│   │   ├── prompts.py        # System instructions & brand tone constraints
│   │   ├── sentiment.py      # LLM sentiment engine with LRU query caching
│   │   └── state.py          # SupportAgentState schema
│   ├── rag/
│   │   ├── indexer.py        # Elasticsearch mapping & bulk index lifecycle
│   │   ├── retriever.py      # BM25 + kNN hybrid retriever with compound scoring
│   │   └── embeddings.py     # In-cluster Elasticsearch dense inference client
│   ├── data/                 # Dataset preprocessing & PII extraction pipeline
│   └── eval/                 # LLM-as-a-judge evaluation suite
├── data/                     # Local SQLite database & processed datasets
├── tests/                    # Unit and integration test suites
├── main.py                   # CLI entrypoint (interactive, query, eval, indexing)
└── pyproject.toml
```

---

## Quickstart

### 1. Environment Configuration

Create `.env` in the root directory:

```env
# Elasticsearch Cloud Serverless
ELASTICSEARCH_ENDPOINT="https://<cluster-id>.es.<region>.aws.elastic.cloud:443"
ELASTICSEARCH_API_KEY="<api-key>"

# Primary LLM Provider (Default: Groq)
GROQ_API_KEY="gsk_..."
GROQ_MODEL="openai/gpt-oss-120b"

# Optional LLM Providers
GEMINI_API_KEY="AIzaSy..."
GEMINI_MODEL="gemini-3.8-flash"
OPENAI_API_KEY="sk-..."
OPENAI_MODEL="gpt-4o-mini"

# Retrieval Threshold
RAG_CONFIDENCE_THRESHOLD=20.0
```

### 2. Run Web Application

**Terminal 1 — Backend (FastAPI + WebSockets):**
```bash
uv sync
uv run uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

**Terminal 2 — Frontend (Vite + React):**
```bash
cd frontend
npm install
npm run dev
```

- **Customer Chat**: [http://localhost:5173](http://localhost:5173)
- **Agent Console**: [http://localhost:5173/agent](http://localhost:5173/agent)
- **API Documentation**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

*Note: You can also build the frontend (`npm run build`), and FastAPI will automatically serve the production bundle from the root URL.*

### 3. Run CLI Interface

```bash
# Interactive multi-turn CLI session
uv run python main.py

# Single-query execution
uv run python main.py -q "Spotify keeps skipping tracks on my Anker bluetooth speaker"
```

---

## Human-in-the-Loop (HITL) Workflow

The system uses a **dual-checkpoint gate** to decide when human intervention is required:

1. **Pre-Retrieval Gate**:
   - Intent: Account security, billing disputes, or credentials.
   - Sentiment: Frustration score $\ge 0.5$, sarcastic tone, or explicit requests for a representative.
2. **Post-Retrieval Gate**:
   - RAG Confidence: Compound score $< 20.0$ against historical cases.

```
Customer triggers HITL
  └─► Agent generates Ticket (e.g. SPOTIFY-T2-78412)
  └─► Saved to SQLite (status: hitl_pending)
  └─► WebSocket event (hitl_new) broadcast to /ws/agent
  └─► Agent Console displays ticket with diagnostics & reasoning
  └─► Agent clicks "Claim Ticket" (status: human_active)
  └─► Live two-way WebSocket chat takeover between customer and human agent
  └─► Agent marks "Resolve" (status: closed)
```

---

## Knowledge Base & Elasticsearch Setup

To rebuild the vector index from raw Twitter customer support data:

1. **Place raw dataset**: Download [Customer Support on Twitter](https://www.kaggle.com/datasets/thoughtvector/customer-support-on-twitter) and place `twcs.csv` in `dataset/twcs.csv`.
2. **Extract & Clean Threads**:
   ```bash
   uv run python src/data/extract_spotify_threads.py --input dataset/twcs.csv --output_dir data/processed
   ```
3. **Index into Elasticsearch**:
   ```bash
   uv run python main.py --index --recreate
   ```

### Hybrid Retrieval Scoring

$$\text{Score} = \text{BM25}(q, d) + (\text{Cosine}(v_q, v_d) \times 0.8)$$

- **Score $< 20.0$**: Low relevance match $\rightarrow$ intercepted and escalated to HITL.
- **Score $25.0 - 32.0$**: Moderate semantic match $\rightarrow$ synthesized into step-by-step guidance.
- **Score $\ge 35.0$**: High-confidence match $\rightarrow$ verified device-specific resolution.

---

## Testing & Evaluation

```bash
# Run full test suite
uv run pytest

# Run targeted subsystem tests
uv run pytest tests/test_hitl_escalation.py -v
uv run pytest tests/test_agent_graph.py -v
uv run pytest tests/test_retriever.py -v

# Run LLM-as-a-Judge benchmark evaluation
uv run python main.py --eval
# or
uv run python src/eval/llm_judge.py
```
