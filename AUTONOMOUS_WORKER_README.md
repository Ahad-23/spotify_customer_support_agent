# CentrAlign AI Employee: Autonomous Enterprise Task Worker

An autonomous AI task worker prototype built for enterprise operations. It accepts high-level natural language instructions, autonomously plans multi-step execution sequences, drives real enterprise software (osTicket) via browser automation, dynamically observes and adapts to errors in real time, and independently verifies outcomes with visual screenshot evidence.

---

## 1. System Architecture

The solution implements a **Hierarchical Two-Tier StateGraph Architecture** that decouples general computer-use task execution from domain-specific intelligence.

### 1.1 End-to-End System & Runtime Topology

```mermaid
flowchart TD
    subgraph Client["Presentation Layer (React 19 + Vite)"]
        UI["Task Dashboard (/tasks)\n• Live Action Log Timeline\n• Real-Time WebSocket Streaming\n• Screenshot Lightbox & Evidence Gallery\n• Interactive Approval / Clarification Modal"]
    end

    subgraph API["Backend Service Layer (FastAPI + SQLite)"]
        REST["Task Management API\n• POST /api/tasks (Dispatch)\n• GET /api/tasks/{id} (Poll)\n• POST /api/tasks/{id}/resume (Approval)"]
        WS["WebSocket Streaming\n• /ws/tasks (Live step logs)"]
        DB[(SQLite Task Store\n• Status, Plan DAG, Evidence, Memory)]
    end

    subgraph WorkerCore["Tier 1: Autonomous Task Worker (src/worker/graph.py)"]
        PLANNER["1. Planner Node\n• Intent Decomposition\n• Ordered DAG Generation"]
        EXECUTOR["2. Executor Node\n• Tool Dispatching\n• Param Token Substitution"]
        OBSERVER["3. Observer Node\n• Live DOM Inspection\n• Real-Time Adaptive Recovery"]
        VERIFIER["4. Verifier Node\n• Independent DOM Inspection\n• Visual Evidence Capture"]
        REPORTER["5. Reporter Node\n• Markdown Summary\n• Metric Compilation"]
        CLARIFIER["6. Clarifier Gate\n• Pauses for Operator Approval"]
    end

    subgraph Tools["Execution & Intelligence Tool Registry"]
        BROWSER["Browser Tool (Playwright)\n• Headless Chromium Engine\n• Progressive Candidate Discovery\n• DOM Event Dispatching"]
        SUPPORT["Support Agent Tool (CBR RAG)\n• Invokes Tier-2 Domain Brain\n• Intent + Pinecone Retrieval"]
        HTTP_TOOL["HTTP API Tool (httpx)\n• REST Integration"]
    end

    subgraph EnterpriseApp["Target Enterprise Environment (Docker)"]
        OSTICKET["osTicket Helpdesk v1.15\n• http://localhost:8088/scp\n• Ticket Queues, Users, Tasks, Dashboard"]
        MARIADB[("MariaDB 10.11\n• Persistent DB State")]
    end

    UI <-->|REST & WS| API
    API <--> WorkerCore
    API --- DB
    EXECUTOR --> Tools
    VERIFIER --> BROWSER
    BROWSER <-->|Playwright Automation| OSTICKET
    OSTICKET --- MARIADB
```

---

### 1.2 Core Execution & Adaptive Recovery Lifecycle

The Task Worker executes tasks through a **Closed-Loop Act-Observe-Decide Cycle**:

```mermaid
flowchart TD
    START([User Natural Language Task]) --> P[Planner Node]
    
    P -->|Ambiguous Request| CLARIFY[Clarification Gate\nStatus: awaiting_user]
    CLARIFY -->|Human Input Provided| P
    
    P -->|Valid DAG Generated| EXEC[Executor Node\nExecute Step i]
    
    subgraph ClosedLoop["Closed-Loop Real-Time Recovery Cycle"]
        EXEC --> OBS[Observer Node\nInspect Live Output & Errors]
        OBS -->|Step Succeeded| CHECK_MORE{More Steps in Plan?}
        CHECK_MORE -->|Yes| NEXT_STEP[Increment step_index] --> EXEC
        
        OBS -->|Step Failed / Stumbled| ADAPT{Retries < Max Retries?}
        ADAPT -->|Yes: Alternative Selector / Text Match| INJECT[Inject alternative_params / steps] --> EXEC
        ADAPT -->|No: Unrecoverable| CLARIFY
    end

    CHECK_MORE -->|All Steps Complete| VERIFY[Verifier Node\nIndependent DOM Query & Screenshot]
    
    VERIFY -->|Verified: Status Correct| REPORT[Reporter Node\nCompile Summary & Artifacts]
    VERIFY -->|Unverified: Status Still Open| REPORT_FAIL[Reporter Node\nFlag Failure & Unresolved State]
    
    REPORT --> DONE([Task Completed + Verified Evidence])
    REPORT_FAIL --> FAILED([Task Failed + Detailed Diagnostic])
```

---

### 1.3 State Node Responsibilities

| State Node | Module Path | Core Responsibilities |
|---|---|---|
| **Planner** | [`src/worker/planner.py`](file:///c:/Users/Ahad/Documents/repos/customer_support_agent/src/worker/planner.py) | Analyzes natural language instructions, detects ambiguity, structures goal definition, and generates an ordered sequence of typed `PlanStep` actions. |
| **Executor** | [`src/worker/executor.py`](file:///c:/Users/Ahad/Documents/repos/customer_support_agent/src/worker/executor.py) | Resolves dynamic memory variables (`{last_output}`, `{support_response}`, `{ticket_reply_status}`), enforces security credentials, and dispatches actions to tool implementations. |
| **Observer** | [`src/worker/observer.py`](file:///c:/Users/Ahad/Documents/repos/customer_support_agent/src/worker/observer.py) | Closed-loop feedback controller: inspects tool execution output, detects errors/timeouts, and dynamically generates alternative selectors or steps in real time without aborting the task. |
| **Verifier** | [`src/worker/verifier.py`](file:///c:/Users/Ahad/Documents/repos/customer_support_agent/src/worker/verifier.py) | Independently formulates verification checks, inspects actual live DOM entity states (e.g., verifying `Status: Resolved` vs `Status: Open`), captures screenshot evidence, and rejects false-positive completions. |
| **Reporter** | [`src/worker/reporter.py`](file:///c:/Users/Ahad/Documents/repos/customer_support_agent/src/worker/reporter.py) | Compiles structured Markdown execution summaries, action counts, retry metrics, and attached screenshot galleries for human operators. |

---

## 2. Setup & Run Instructions

### Prerequisites
- **Python 3.11+** with [`uv`](https://github.com/astral-sh/uv)
- **Node.js 18+** & `npm`
- **Docker Desktop** (for running osTicket & MariaDB)

---

### Step 1: Environment Configuration
Create a `.env` file in the root directory (or copy `.env.example`):

```env
# LLM Provider Keys (Groq / Gemini / OpenAI via LiteLLM)
GROQ_API_KEY="gsk_..."
GROQ_MODEL="groq/openai/gpt-oss-120b"
GEMINI_API_KEY="AQ..."
GEMINI_MODEL="gemini-3.8-flash"
LLM_MODEL="groq/openai/gpt-oss-120b"
FALLBACK_MODELS="groq/openai/gpt-oss-20b,groq/qwen/qwen3.8-27b"

# osTicket Helpdesk Integration
OSTICKET_URL="http://localhost:8088"
OSTICKET_STAFF_USER="ostadmin"
OSTICKET_STAFF_PASS="Admin1"

# Vector Search (Optional for Domain Brain)
PINECONE_API_KEY="pcsk_..."
PINECONE_INDEX_NAME="spotify-support-cases"
```

---

### Step 2: Start Services

#### 1. Start osTicket Helpdesk (Docker)
```bash
docker compose -f osticket/docker-compose.yml up -d
```
*osTicket is accessible at `http://localhost:8088` (Staff Control Panel at `http://localhost:8088/scp`).*

#### 2. Start Backend API (FastAPI + WebSockets)
```bash
uv sync
uv run uvicorn backend.main:app --reload --port 8000
```

#### 3. Start Frontend Web App (React 19 + Vite)
```bash
cd frontend-web
npm install
npm run dev
```

---

### Step 3: Access Interfaces
- **Autonomous Task Dashboard:** [`http://localhost:5173/tasks`](http://localhost:5173/tasks) — Interactive task runner with live step execution traces, screenshot lightbox, and manual approval gates.
- **Customer Chat & HITL Console:** [`http://localhost:5173`](http://localhost:5173) and [`http://localhost:5173/agent`](http://localhost:5173/agent).
- **FastAPI OpenAPI Documentation:** [`http://localhost:8000/docs`](http://localhost:8000/docs).

---

### Step 4: Run Automated Tests
```bash
# Run all 169 unit & integration tests
uv run pytest
```

---

## 3. In-Depth Technical Documentation

For complete technical specifications, design decisions, known limitations, assumptions, future roadmap, and component breakdowns, refer to:
👉 **[AUTONOMOUS_WORKER_TECHNICAL_DOCS.md](AUTONOMOUS_WORKER_TECHNICAL_DOCS.md)**
