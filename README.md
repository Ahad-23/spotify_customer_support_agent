# SpotifyCares AI Support Platform

A Case-Based Reasoning (CBR) customer support platform with real-time Human-in-the-Loop (HITL) handoff. Powered by **LangGraph**, **Pinecone Serverless** vector search, **FastAPI + WebSockets**, **React 19**, and **React Native / Expo**.

---

## System Architecture

```mermaid
flowchart TD
    subgraph Clients["Frontend Clients"]
        WEB["React 19 Web App (Vite)\n• Customer Chat (/)\n• Agent Console (/agent)"]
        MOB["React Native Mobile App (Expo)\n• Customer Chat Screen\n• Agent Dashboard Screen"]
    end

    subgraph API["Backend (FastAPI + SQLite)"]
        REST["REST Endpoints\n/api/sessions, /api/agents"]
        WS["WebSocket Manager\n/ws/sessions/{id}, /ws/agents"]
        DB[(SQLite / support.db\nSessions, Messages, Tickets)]
    end

    subgraph Core["Agent Core (LangGraph)"]
        IA["Intent & Sentiment Analyzer\n• Device detection\n• Frustration scoring (LiteLLM)"]
        CR["Case Retriever (CBR)\n• Pinecone Serverless (Cosine)\n• multilingual-e5-large (1024d)"]
        SG["Solution Generator\n• Groq / Gemini / OpenAI\n• Deterministic Fallback"]
        HITL["HITL Escalation Node\n• Structured Ticket Dispatch\n• SPOTIFY-T2-#####"]
    end

    WEB <-->|REST & WS| API
    MOB <-->|REST & WS| API
    API <--> Core
    API --- DB

    IA -->|Billing / Account Security| HITL
    IA -->|Frustration >= 0.5 / Agent Request| HITL
    IA -->|Standard Troubleshooting| CR
    CR -->|Relevance < 0.70| HITL
    CR -->|Relevance >= 0.70| SG
    HITL -.->|Real-time alert| Clients
```

---

## Tech Stack

| Layer | Technologies |
|---|---|
| **Web Frontend** | React 19, TypeScript, Vite, Tailwind CSS v4, Marked, DOMPurify |
| **Mobile Frontend** | React Native, Expo SDK 57, React Navigation, Expo Constants, AsyncStorage |
| **Backend** | FastAPI, Uvicorn, SQLAlchemy, SQLite, WebSockets, Pydantic v2 |
| **Agent & Inference** | LangGraph, LiteLLM (Groq `groq/openai/gpt-oss-120b`, fallback Gemini `gemini-3.8-flash`) |
| **Search & Retrieval** | Pinecone Serverless, multilingual-e5-large (1024d dense vectors via Pinecone Inference) |
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
│   │   └── ws.py             # WebSocket routes (/ws/sessions, /ws/agents)
│   ├── services/
│   │   ├── chat_service.py   # Agent execution wrapper & session state sync
│   │   └── websocket_manager.py # Real-time pub/sub connection manager
│   └── main.py               # FastAPI entrypoint, dynamic CORS & static mount
├── frontend-web/             # React 19 SPA (Spotify dark theme)
│   ├── src/
│   │   ├── pages/
│   │   │   ├── CustomerChat.tsx   # Customer conversational interface
│   │   │   └── AgentDashboard.tsx # HITL agent queue & live chat takeover
│   │   ├── components/       # MessageBubble, TicketCard, ChatInput, MarkdownContent
│   │   ├── hooks/            # useWebSocket hook
│   │   └── api/client.ts     # Typed fetch client
│   ├── vite.config.ts        # Vite dev server with /api and /ws proxy
│   └── package.json
├── frontend-mobile/          # React Native / Expo app (Spotify dark theme)
│   ├── src/
│   │   ├── screens/
│   │   │   ├── CustomerChatScreen.tsx   # Mobile chat with live server switcher
│   │   │   └── AgentDashboardScreen.tsx # Mobile HITL agent queue & takeover
│   │   ├── components/       # MessageBubble, ChatInput, TicketCard
│   │   ├── hooks/            # useWebSocket auto-reconnecting hook
│   │   └── api/client.ts     # Dynamic host discovery client (Expo Constants)
│   ├── App.tsx               # Native Stack Navigation entrypoint
│   ├── .env                  # Optional EXPO_PUBLIC_API_BASE_URL override
│   └── package.json
├── src/                      # Core agent & RAG pipeline
│   ├── agent/
│   │   ├── graph.py          # LangGraph StateGraph & conditional edge routing
│   │   ├── nodes.py          # Analyzer, retriever, generator, escalation nodes
│   │   ├── prompts.py        # System instructions & brand tone constraints
│   │   ├── sentiment.py      # LLM sentiment engine with LRU query caching
│   │   └── state.py          # SupportAgentState schema
│   ├── rag/
│   │   ├── indexer.py        # Pinecone Serverless index & bulk upsert lifecycle
│   │   ├── retriever.py      # Pinecone dense vector retriever with metadata filtering
│   │   └── embeddings.py     # Pinecone Inference embedding client (multilingual-e5-large)
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
# Pinecone Serverless Configuration
PINECONE_API_KEY="pcsk_..."
PINECONE_INDEX_NAME="spotify-support-cases"
PINECONE_CLOUD="aws"
PINECONE_REGION="us-east-1"

# Primary LLM Provider (Default: Groq)
GROQ_API_KEY="gsk_..."
GROQ_MODEL="groq/openai/gpt-oss-120b"
LLM_MODEL="groq/openai/gpt-oss-120b"

# Optional Fallback Provider
GEMINI_API_KEY="AQ.Ab8RN..."
GEMINI_MODEL="gemini-3.8-flash"

# Retrieval Threshold (Cosine similarity: 0.0 to 1.0)
RAG_CONFIDENCE_THRESHOLD=0.70
```

---

### 2. Run Backend & Frontend Applications

#### Terminal 1 — Backend (FastAPI + WebSockets)
```bash
uv sync
uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```
*Note: Binding to `0.0.0.0` allows physical mobile devices on your Wi-Fi or mobile hotspot to connect.*

#### Terminal 2 — Web Frontend (React 19 + Vite)
```bash
cd frontend-web
npm install
npm run dev
```
* **Customer Chat**: [http://localhost:5173](http://localhost:5173)
* **Agent Console**: [http://localhost:5173/agent](http://localhost:5173/agent)
* **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)

#### Terminal 3 — Mobile Frontend (React Native / Expo)
```bash
cd frontend-mobile
npm install
npx expo start
```
Scan the QR code with **Expo Go** on iOS or Android, or press:
* `a` — Android emulator
* `i` — iOS simulator
* `w` — Web browser preview

**Mobile Connection & Auto-Discovery**:
* The mobile app uses **dynamic host resolution** via `expo-constants`. When opening via Expo Go, it automatically extracts your development machine's IP without requiring any manual IP configuration.
* Tap **Server Settings** in the top-right header of the mobile app to switch between:
  * **Auto-detected Host** (Wi-Fi / Hotspot IP)
  * **Android Emulator** (`http://10.0.2.2:8000`)
  * **Localhost** (`http://localhost:8000`)
  * Custom API URL
* **Mobile Hotspot / Windows Note**: If your laptop is connected to your phone's mobile hotspot, ensure your Wi-Fi network profile in Windows Settings is set to **Private** so Windows Defender Firewall permits incoming connections on port 8000.

---

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
   - RAG Confidence: Cosine similarity score $< 0.70$ against historical cases.

```
Customer triggers HITL
  └─► Agent generates Ticket (e.g. SPOTIFY-T2-78412)
  └─► Saved to SQLite (status: hitl_pending)
  └─► WebSocket event (hitl_new) broadcast to /ws/agents
  └─► Agent Console (Web & Mobile) displays ticket with diagnostics
  └─► Agent clicks "Claim Ticket" (status: human_active)
  └─► Live two-way WebSocket chat takeover between customer and human agent
  └─► Agent marks "Resolve" (status: closed)
```

---

## Knowledge Base & Pinecone Setup

To rebuild the vector index from raw Twitter customer support data:

1. **Place raw dataset**: Download [Customer Support on Twitter](https://www.kaggle.com/datasets/thoughtvector/customer-support-on-twitter) and place `twcs.csv` in `dataset/twcs.csv`.
2. **Extract & Clean Threads**:
   ```bash
   uv run python src/data/extract_spotify_threads.py --input dataset/twcs.csv --output_dir data/processed
   ```
3. **Index into Pinecone**:
   ```bash
   uv run python main.py --index --recreate
   ```

### Cosine Similarity Scoring

$$\text{Score} = \text{Cosine}(v_q, v_d)$$

- **Score $< 0.70$**: Low relevance match $\rightarrow$ intercepted and escalated to HITL.
- **Score $0.70 - 0.85$**: Moderate semantic match $\rightarrow$ synthesized into step-by-step guidance.
- **Score $\ge 0.85$**: High-confidence match $\rightarrow$ verified device-specific resolution.

---

## Testing & Evaluation

```bash
# Run full test suite (138 tests)
uv run pytest

# Run autonomous worker tests
uv run pytest tests/test_autonomous*.py -v

# Run targeted subsystem tests
uv run pytest tests/test_hitl_escalation.py -v
uv run pytest tests/test_agent_graph.py -v
uv run pytest tests/test_retriever.py -v

# Run LLM-as-a-Judge benchmark evaluation
uv run python main.py --eval
# or
uv run python src/eval/llm_judge.py
```

---

## Autonomous AI Task Worker (osTicket Integration)

An autonomous execution agent that completes natural language support operations using computers, real browser automation (Playwright), and ticketing systems (osTicket).

### Cyclic Act-Observe-Decide Architecture

```mermaid
flowchart LR
    Task([Natural Language Task]) --> Planner[Planner Node\nGoal + Step Decomposition]
    Planner -->|Ambiguous| Clarifier[Clarifier Gate\nPause for User Input]
    Planner -->|Plan Ready| Executor[Executor Node\nPlaywright / HTTP Dispatch]
    
    subgraph CoreLoop["Act-Observe-Decide Cycle"]
        Executor --> Observer[Observer Node\nInspect Output & Screenshots]
        Observer -->|Step Succeeded| NextStep{More Steps?}
        NextStep -->|Yes| Executor
        Observer -->|Failure Detected| Retry{Retries < Max?}
        Retry -->|Yes: Alternative params| Executor
        Retry -->|No / Ambiguous| Clarifier
    end

    NextStep -->|All Steps Done| Verifier[Verifier Node\nIndependent State Check]
    Verifier --> Reporter[Reporter Node\nSummary & Evidence]
    Clarifier -->|User Resumes| Planner
    Reporter --> Done([Task Completed / Evidence])
```

### 11 System Capabilities

| Capability | Implementation | Evidence |
|---|---|---|
| **C1: Goal Understanding** | `planner.py` extracts canonical goal and support context from raw requests | Extracted goal in state & logs |
| **C2: Action Decomposition** | `planner.py` breaks task into typed `PlanStep` sequences | Structured plan steps |
| **C3: Tool Dispatch** | `ToolRegistry` with Playwright browser & HTTP API tools | DOM automation & API calls |
| **C4: Result Observation** | `observer.py` analyzes action text and captured screenshots | Step status & memory updates |
| **C5: Dynamic Deciding** | Decides next action, retry, or alternative path based on runtime state | State machine transitions |
| **C6: Working Memory** | `state.memory` stores ticket IDs, department IDs, customer emails | Persistent memory across steps |
| **C7: Failure Detection** | Detects HTTP errors, validation errors, timeouts, or incorrect DOM states | Error classification |
| **C8: Error Recovery** | Retries failed steps with alternative selectors or adapted payloads | Automatic retry counter |
| **C9: Outcome Verification** | `verifier.py` inspects created tickets and validates fields match the goal | Verification pass/fail verdict |
| **C10: Clarification Gate** | Pauses graph when ambiguous or dangerous, awaits user approval | `awaiting_user` state & UI modal |
| **C11: Evidence Report** | `reporter.py` compiles Markdown summary, retries count, and screenshots | Final summary + screenshots |

### Running the Autonomous Worker

#### 1. Start osTicket Helpdesk (Docker)
```bash
docker compose -f osticket/docker-compose.yml up -d
# Accessible at http://localhost:8088 (staff panel at /scp/)
```

#### 2. Seed osTicket with Demo Support Data
```bash
uv run python -m osticket.seed
```

#### 3. Run Autonomous Tasks

**Via CLI**:
```bash
uv run python main.py --task "Create a high-priority ticket for john@example.com about Bluetooth audio skipping on Android"
```

**Via Web Dashboard**:
1. Start backend: `uv run uvicorn backend.main:app --reload --port 8000`
2. Start frontend: `npm --prefix frontend-web run dev`
3. Navigate to `http://localhost:5173/tasks` for the interactive Task Dashboard.

**Via REST API**:
```bash
# Submit task
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"task": "Create ticket for john@example.com reporting playlist sync issues"}'

# Poll task status
curl http://localhost:8000/api/tasks/{task_id}

# Resume paused task (clarification gate)
curl -X POST http://localhost:8000/api/tasks/{task_id}/resume \
  -H "Content-Type: application/json" \
  -d '{"user_input": "Assign to Tier-1 Audio and proceed"}'
```

