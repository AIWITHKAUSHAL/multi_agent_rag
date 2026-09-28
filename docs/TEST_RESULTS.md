# Verification results

Recorded on **26 September 2026** on macOS / Apple Silicon with Python 3.12.13.

| Check | Observed result | Scope |
|---|---|---|
| `pytest -q` | **60 passed**, 1 dependency deprecation warning | Component and API/orchestration tests with isolated test doubles / mocked provider HTTP |
| `ruff check app tests scripts` | **Passed** | Python static analysis |
| Ruff docstring and formatting checks | **Passed** | Public application/script docstrings required; 20 Python files formatted |
| `python -m compileall -q app scripts` | **Passed** | Python syntax/import compilation |
| `node --check app/static/app.js` | **Passed** | Frontend JavaScript syntax |
| Real embedding initialization | **Passed**, vector shape `(1, 384)` | Actual downloaded `BAAI/bge-small-en-v1.5` model on CPU |
| Real HTTP document ingestion | **Passed** | Handbook: 3 chunks; project requirements: 2 chunks, persistent SQLite storage |
| Real semantic retrieval | **Passed manual spot checks**, details below | Local model and actual example document, no fake vectors |
| Headless Chrome UI check | **Passed**, no JavaScript errors | Real uploads, deduplication, chunk dialog, tabs, suggested query, missing-key behavior |
| Responsive checks | **Passed** at 1440, 1024 and 390 px | Screenshots inspected at desktop/mobile; no horizontal overflow |
| `docker compose config --quiet` | **Passed** | Compose syntax only; container build/runtime not exercised |
| Architecture SVG | **Passed XML validation** | Repository-native diagram |
| Query case inventory | **36 unique cases**, 6 per category | Direct, document, tool, multi-step, follow-up and failure |
| Live EURI preflight | **Blocked: EURI_API_KEY missing** | No real model completion was possible |
| 36-query live end-to-end evaluation | **Not run beyond preflight** | No live answer quality or Gemini account/model availability claim |

The dependency warning concerns Starlette's deprecated use of `httpx` in `TestClient`; it did not affect the 60 test outcomes. Production API requests use FastAPI/Uvicorn; the test client's warning is not a model/provider failure.

## Automated coverage

- Page-aware chunks, exact character offsets, overlap continuity and invalid chunk settings.
- Rejection of empty, binary, invalid UTF-8, malformed PDF, scanned PDF and encrypted PDF uploads.
- Persistent vectors, content deduplication, Top-K ranking, metadata filtering, minimum similarity, document deletion and embedding-model mismatches.
- Safe arithmetic, operator coverage, prevention of code/function execution, resource bounds, division by zero, time zones and dates.
- Six-agent order, actual tool invocation under a test-selected plan, conversational history, session separation and same-session concurrency guard.
- Empty-evidence abstention, successful revision, bounded repeated rejection, and invented citation rejection even when a test critic approves.
- Interrupted-run recovery, HTTP upload/query validation, missing-key errors, run inspection and SSE cursor replay.
- EURI-compatible request URL/model/messages, sanitized provider status failures, one JSON repair, failed repair, empty responses and truncated responses.

These tests are engineering checks, not the assignment's real 30+ question demonstration. The production application has no test-double or canned-answer setting.

## Real semantic retrieval spot checks

Executed against the uploaded handbook using the real local model. Chunk numbers below are 1-based. These are observed similarity scores, not confidence percentages.

| Query | Highest-ranked handbook chunk | Cosine similarity |
|---|---:|---:|
| base course fee and GST | 1 | 0.7786 |
| refund for cancellation | 2 | 0.6657 |
| minimum attendance certificate | 3 | 0.7069 |
| instructor name | 1 | 0.6191 |
| capstone marks video and code | 2 | 0.6997 |

The two example documents were also uploaded through the actual UI. Browser checks found a missing empty-state placeholder in the Sources tab; it was fixed and the browser checks then passed. Desktop and mobile screenshots are in `reports/ui-desktop.png` and `reports/ui-mobile.png`.

## Complete the live evidence

1. Add a valid `EURI_API_KEY` to `.env` and restart the application.
2. Run `uv run python scripts/preflight.py --check-provider`. Confirm the returned model is acceptable for your account/lesson.
3. Run `uv run python scripts/evaluate.py` against the running server. It makes real provider requests and consumes quota.
4. Inspect `reports/live-results.json` and `reports/live-results.md`. Record failures accurately; do not replace them with expected results.
5. Manually review citations against passages, arithmetic operands, follow-up resolution, prompt-injection handling and appropriate refusals. Automated patterns cannot prove these semantic properties.
6. Add a sanitized, reviewed live report to the public repository and show those results in the video.

GitHub publication and YouTube recording/upload have not been performed by this verification run.

## Documentation and teaching-visual update

After adding module/class/function docstrings, the existing suite was rerun: **60 passed**.
Ruff lint (including the new docstring rules), Ruff format checking, and frontend/render-script
JavaScript syntax checks passed. No model behavior was changed by this documentation update.

The [visual collection](visuals/README.md) includes an illustrated architecture overview and
three code-accurate companion diagrams. Companion PNGs were rendered at **3840×2160 (16:9)**,
their text bounds were checked in Chrome, and all three exports were visually inspected.
Editable SVGs and regeneration scripts are included. The overview uses the built-in image
generation tool's original resolution; exact dimensions and the prompt are documented in the gallery.
