# Video recording outline — approximately 12–15 minutes

Record the real local application with your configured EURI account. This file is a script, not a claim that a video has been recorded or uploaded.

| Time | Screen | Explanation / action |
|---|---|---|
| 0:00–0:45 | UI and README | State the capstone goal, six agents, real provider and complete RAG pipeline |
| 0:45–2:15 | `docs/architecture.svg` | Explain every handoff; distinguish routing, planning, tools and critic revision |
| 2:15–3:00 | Configuration names, no secret values | Explain EURI base URL/model and local embeddings; click Check connection |
| 3:00–4:30 | `main.py`, `schemas.py`, `orchestrator.py` | Show typed requests, sessions, shared state, sequential calls, one revision limit and SSE events |
| 4:30–5:45 | `agents.py` | Show specialist prompts/contracts, routing and grounded generation |
| 5:45–6:45 | `retrieval.py`, `store.py` | Show extraction, overlap, vectors, metadata, cosine ranking and Top-K |
| 6:45–7:30 | `tools.py`, `llm.py` | Show safe AST calculation and real EURI call; never show the key |
| 7:30–8:30 | UI | Upload a source document live, inspect actual chunks |
| 8:30–9:15 | UI | Ask a direct concept question and explain skipped stages |
| 9:15–10:15 | UI | Ask document fee/refund question, expand trace and sources, map citation |
| 10:15–11:15 | UI | Retrieve fee/GST and compute three-student total; follow up for two students |
| 11:15–12:00 | UI | Demonstrate division by zero and missing document information |
| 12:00–13:15 | Terminal and reports | Show automated tests, 36 real query results, honest failures and manual review |
| 13:15–14:00 | API docs and GitHub | Show endpoints, setup instructions, architecture and submitted artifacts |

Suggested narration for the multi-step query:

“The router recognizes that this requires document facts and arithmetic. The planner asks retrieval for the base fee and GST. The retrieval agent selects actual source chunks. The tool agent fills a calculator expression from those values. The execution agent combines the result with citations. The critic checks whether the evidence and computation support the answer. We can inspect every stage rather than accepting an unexplained response.”

Before publishing, verify the video includes an architecture explanation, enough readable code to substantiate the patterns, uploads and complete live answers. Use readable zoom, hide personal notifications and `.env`, and show model/network latency honestly. If you cut waiting time, label the edit. Include a link to the public repository in the YouTube description and place the final video URL in README.
