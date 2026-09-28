# Follow the code, file by file

There are two main paths: upload documents to build the evidence library, then ask questions
against that library. Configuration, schemas, storage, and model access support those paths;
they are not additional agents in the six-agent sequence.

The [four-image visual collection](visuals/README.md) provides the presentation version of this guide.

## 1. Boot: connect the components

```text
uvicorn app.main:create_app --factory
  → main.py: create_app()
      → config.py: Settings()               reads environment / .env
      → store.py: Store(...)                creates SQLite tables if needed
      → llm.py: LLM(settings)               configures the EURI HTTP client
      → retrieval.py: Embedder(settings)    prepares lazy model loading
      → retrieval.py: Retriever(...)        connects embeddings to storage
      → orchestrator.py: Orchestrator(...)  prepares queue/concurrency controls
  → main.py: lifespan()
      → store.py: recover_runs()            fails work interrupted by a prior restart
```

Creating the app does not make an EURI request or download embeddings. The embedding model
loads on the first `Embedder.encode()` call. The provider connection button makes its own real request.

## 2. Upload: turn bytes into searchable evidence

```text
static/app.js: uploadFiles(files)
  → POST /api/documents
  → main.py: upload(file)
      → validate size, serialize mutations
      → asyncio.to_thread(retriever.ingest, name, content)
  → retrieval.py: Retriever.ingest()
      → extract_pages()                     PDF pages or one TXT/MD logical page
      → chunk_pages()                       overlapping slices and page offsets
      → Store.documents()                   check content/configuration fingerprint
      → Embedder.encode(chunk_texts)        skipped for duplicate content
      → store.py: Store.insert_document()   atomic metadata + chunks + vectors
  ← metadata and created flag
  ← main.py returns HTTP 201
  → static/app.js: loadDocuments()          refreshes the visible library
```

Clicking **Inspect chunks** follows a different read-only path:
`app.js → GET /api/documents/{id}/chunks → main.chunks() → Store.document_chunks()`.

## 3. Question: route, plan, retrieve, compute, write, check

```text
static/app.js: chat-form submit
  → POST /api/runs
  → schemas.py: QueryRequest                FastAPI validates the request body
  → main.py: query(request)                 checks credentials, session and scope
  → orchestrator.py: start(request)         persists a queued run, schedules a task
  ← HTTP 202 {id: run_id}

Background task: Orchestrator.run()
  → Store.history() + Store.documents()
  → invoke(SupervisorAgent) → state['route']
  → invoke(PlanningAgent)   → state['plan']
  → invoke(RetrievalAgent)  → state['sources']
  → invoke(ToolAgent)       → state['tools']
  → invoke(ExecutionAgent)  → state['answer']
  → invoke(ReflectionAgent) → state['critique']
      → if rejected: invoke Execution, then Reflection once more
      → if still rejected: withhold draft and return safe refusal / needs_review
  → Store.save_turn() + Store.update_run()
```

The orchestrator invokes each role; agents do **not** directly invoke the next agent.
`invoke()` emits timing/status events around the role's `run()` method. All six roles are classes
inside `agents.py`, with separate prompts/contracts and responsibilities.

| Agent in `agents.py` | Calls next | Reads → writes |
|---|---|---|
| `SupervisorAgent.run()` | `LLM.structured(..., Route)` | question + history + document names → `route` |
| `PlanningAgent.run()` | `LLM.structured(..., Plan)` | question + route → `plan` |
| `RetrievalAgent.run()` | `Retriever.search()` → `Embedder.encode(query=True)` → `Store.search()` | route + plan + document scope → `sources` |
| `ToolAgent.run()` | `LLM.structured(..., ToolSelection)` → `tools.run_tool()` | question + plan + sources → `tools` |
| `ExecutionAgent.run()` | `LLM.complete()` unless required retrieval is empty | question + plan + sources + tools + feedback → `answer` |
| `ReflectionAgent.run()` | `citation_issues()` + `LLM.structured(..., Critique)` unless accepting empty-evidence abstention | answer + sources + tools → `critique` |

The retrieval and tool agents explicitly skip when the route does not need them. The retriever
is a local deterministic specialist. The model is responsible for decisions and wording, while
Python enforces tool restrictions, state progression, citation-ID validity, and revision bounds.

## 4. Live display: how results get back to the browser

```text
Orchestrator.invoke() / emit()
  → store.py: event()                       persists a timestamped event

static/app.js: watchRun(run_id)
  → GET /api/runs/{id}/events               browser EventSource connection
  → main.py: events() / stream()
      → Store.events(after=cursor)          replays ordered trace records
      → Store.get_run()                    checks whether the run is terminal
  ← SSE trace events                       rendered by addEvent()
  ← SSE done event                         rendered by completeRun()
      → renderSources()                    maps [S1] to retrieved passages
```

This streams agent events, not individual model tokens. `Last-Event-ID` supports event replay.
Browser refresh can reconnect to a saved active run; server restart cannot resume an in-memory task.

## Runtime file reference

| File | Responsibility | Called by / loaded by | What it calls or returns |
|---|---|---|---|
| `app/__init__.py` | Declare/document the Python package | Python import system | No pipeline work |
| `app/main.py` | Build services, validate API operations, serve UI and SSE | Uvicorn and HTTP clients | Settings, Store, LLM, Retriever, Orchestrator; HTTP responses |
| `app/config.py` | Read settings and validate chunk overlap | `main.create_app()`, preflight | Pydantic settings; no provider call |
| `app/schemas.py` | Bound API and agent output shapes | FastAPI, agents, LLM validation | Pydantic contracts such as Route/Plan/ToolSelection |
| `app/orchestrator.py` | Queue, sequence, shared state, critique loop, traces | `main.query()` | Agent `.run()` methods and Store persistence |
| `app/agents.py` | Six specialist roles and citation checks | `Orchestrator.invoke()` | LLM, Retriever, and `run_tool()` as needed |
| `app/retrieval.py` | Extract, chunk, embed, deduplicate and search | `main.upload()`, `RetrievalAgent.run()`, preflight | pypdf, FastEmbed, NumPy and Store |
| `app/store.py` | Persist vectors, metadata, sessions, messages, runs/events | Main, orchestrator and retriever | SQLite transactions; NumPy cosine ranking |
| `app/tools.py` | Safe calculator, current time, date difference | ToolAgent and tool tests | AST operators, zoneinfo and datetime; success/error result |
| `app/llm.py` | Live EURI adapter, safe errors and JSON repair | LLM-backed agents, connection check, preflight | AsyncOpenAI → EURI; Pydantic validation |
| `app/static/index.html` | Layout, form controls, dialog and panels | `main.home()` → browser | Loads `style.css` and `app.js` |
| `app/static/style.css` | Responsive appearance and state styling | Browser via index.html | No backend calls; optional font download |
| `app/static/app.js` | Upload/chat actions, sessions, traces, source display | Browser after index.html | Fetch API endpoints, EventSource, safe DOM updates |

## Utilities, tests, and entry files

| File | When it runs | What it calls / produces |
|---|---|---|
| `scripts/preflight.py` | Before class, on request | Settings → Embedder and/or LLM; readiness output, no secret values |
| `scripts/evaluate.py` | With a running app and EURI key | Reads `evaluation/queries.json`; HTTP upload/session/run APIs; writes JSON + Markdown reports |
| `scripts/ui_smoke.mjs` | Optional browser verification | Playwright → local Chrome → real app; screenshots and interaction assertions |
| `scripts/build_diagrams.py` | When updating these teaching diagrams | Writes repository-native SVGs; no EURI calls |
| `scripts/render_diagrams.mjs` | When exporting diagrams | Playwright → local Chrome → SVG files; 3840×2160 PNGs |
| `tests/conftest.py` | Pytest fixture setup | Provides isolated Settings, test embedder and scripted LLM |
| `tests/test_api.py` | Automated test suite | TestClient → app factory/endpoints with injected test doubles |
| `tests/test_orchestration.py` | Automated test suite | Orchestrator + agents + isolated Store; validates order/revision/history |
| `tests/test_retrieval.py` | Automated test suite | Extraction/chunking/Retriever/Store; validates metadata and persistence |
| `tests/test_tools.py` | Automated test suite | `calculate()` / `run_tool()`; validates arithmetic restrictions and failures |
| `tests/test_provider.py` | Automated test suite | Real SDK adapter with mocked HTTP transport; validates payload/errors/JSON repair |
| `tests/__init__.py` | Python test imports | Package marker; no application runtime behavior |
| `pyproject.toml` + `uv.lock` | Dependency installation and tool configuration | Define/freeze dependencies, Python version, tests, Ruff/docstring rules |
| `.env` / `.env.example` | Server setup | Actual local secrets / safe example settings; never commit `.env` |
| `Makefile` | Developer shortcuts | Setup, run, test, lint, format, warm and evaluate commands |
| `Dockerfile` + `compose.yaml` | Optional container startup | Install app dependencies, configure data volume, run one Uvicorn worker |
| `.github/workflows/tests.yml` | GitHub push / pull request | Install locked dependencies, Ruff lint/format checks, pytest |

The tests' scripted model and embedder are confined to test setup. None of the production paths
imports `tests/`. The visual exports are teaching assets, not screenshots of a completed live EURI run.

## Docstrings and code quality

Docstrings identify module/class responsibilities and important function inputs, returns,
shared-state writes, persistence side effects, and error behavior. API handler docstrings also
appear in FastAPI's generated documentation. Basic docstring checks are enabled in Ruff for
application and Python scripts; test files retain descriptive test names and assertions.

```bash
make lint                         # Ruff lint + docstring checks + format check
make format                       # apply formatter if needed
uv run pytest -q                  # verify application behavior
```
