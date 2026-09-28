# Teaching Relay live

## Before the students arrive

Set the EURI key in `.env`, start the app, warm the embedding model and verify the provider. A visible configuration indicator is not proof the key works: **Check connection** makes a real provider request. Test the exact model your account enables. Keep the key out of the projected terminal/editor.

Upload the two files under `examples/`. Show students that these are normal source documents and edit a fact, remove/re-upload that document, and ask again if you want to prove answers depend on the actual sources. Uploading a changed file adds a new document, so remove the obsolete version to avoid conflicting evidence.

Use one server worker and one browser session for the main presentation. Start a new chat between unrelated demonstrations. The library is shared; a new chat resets conversation context, not documents. Run the 36-query evaluation before class and retain a reviewed report.

## Explain the architecture with the UI

Open the right-hand agent panel and walk down the six stages. The router is the gatekeeper; the planner decides the work; retrieval finds evidence; the tool agent performs allowed computations; execution writes the answer; the critic checks it. The orchestrator, not the model, enforces the order and the revision limit.

Explain that “agent” means a specialist role with explicit inputs, instructions, outputs and responsibility. It does not imply six separate servers or six different model providers. Five roles make live model calls when needed; the retrieval agent is a deterministic specialist using a real embedding model. Skipped stages still appear in the trace.

Trace explanations are brief operational decisions, not private chain-of-thought. Console logs identify the agent/run/status. The UI/export contains richer evidence, including passages, tool arguments and generated drafts.

## Suggested question sequence

| Question | What to point out |
|---|---|
| Explain RAG in simple terms. | Router skips retrieval/tools for a general concept |
| According to the course handbook, what is the base fee? | Query embedding, Top-K, score, page and source citation |
| What is that including GST? | Session history resolves “that”; calculator returns 14,160 |
| What would that total be for three students? | Multi-step retrieval plus calculation, 42,480 |
| What is the minimum attendance for a certificate? | Document lookup; three out of four sessions |
| What time is it in Asia/Kolkata? | Real clock, not an LLM guess |
| Calculate 10 divided by 0. | Tool error passed to execution and reviewed by critic |
| According to the course handbook, what does campus parking cost? | Missing evidence handled honestly |

If the model routes a question unexpectedly, inspect the route and discuss the limitation. The point of observability is to see actual decisions. Do not claim every question always causes a revision; revisions occur only when the critic rejects a draft. For deterministic code coverage of revision behavior, show the corresponding automated tests.

## Explain RAG concretely

1. Open **Inspect chunks** for the handbook. Show overlap and page-local character offsets. Markdown is treated as a single logical page; PDFs retain actual page numbers.
2. Explain that the embedding model maps a chunk to a 384-value semantic vector. Raw vectors are stored as float32 BLOBs in SQLite alongside the chunk metadata.
3. The planned query gets an embedding from the same model. Normalized vector dot products equal cosine similarity.
4. Change **Retrieved passages** from 2 to 6 and ask the same question in a fresh chat. More passages can help coverage, but can also add irrelevant material.
5. Show the **Sources** tab and map `[S1]` in the answer to the precise passage. Source IDs are local to a run.
6. Explain why similarity is not confidence, why retrieved text is data rather than trusted instructions, and why a critic is useful but fallible.

## Code walkthrough order

Read `app/main.py` (API boundary), `schemas.py` (contracts), `orchestrator.py` (sequence), `agents.py` (specialists), `retrieval.py` and `store.py` (RAG), `tools.py` (safety), and `llm.py` (live integration). Finish at `tests/` and `scripts/evaluate.py` to distinguish deterministic code checks from real end-to-end behavior.

## If something fails during class

| Symptom | Action |
|---|---|
| Missing key banner | Set `.env`, restart; the app reads settings at startup |
| 401/403/404 from EURI | Check key, account/model access and endpoint; do not switch models silently |
| 429/quota | Pause requests and check your EURI account |
| First upload slow | Wait for model download; prewarm before class |
| No text in PDF | Use a text PDF or perform OCR outside this app |
| No useful sources | Check selected documents and the query; inspect scores; tune threshold deliberately |
| Critic rejects twice | Show `needs_review`; refine the question/evidence; the app withholds the draft |
| Browser refresh during run | The saved run reconnects; server restart instead marks it failed |

The app has no canned-answer fallback. If the provider is unavailable, explain the observed failure and resume after connectivity/access is restored.
