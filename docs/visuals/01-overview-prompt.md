# Illustrated overview generation prompt

Tool: built-in image generation (no CLI fallback).

Final prompt used:

```text
Use case: scientific-educational
Asset type: high-quality 16:9 landscape classroom presentation infographic, 3840x2160 if supported.
Primary request: Explain the actual Relay multi-agent RAG code as an elegant, memorable illustrated systems diagram, readable on a projector. Sophisticated isometric editorial illustration integrated with precise large typography, warm ivory background, deep ink text, restrained sage and terracotta accents matching Relay's existing classroom interface. Not a screenshot. No humans or robot mascots. Beautiful subtle dimensional paper/document/vector/chip illustrations, generous whitespace and clean connector arrows.

Title (verbatim): "RELAY / From question to grounded answer"
Subtitle (verbatim): "Six specialist agents. Real retrieval. One reviewed response."

Composition: a clearly numbered horizontal sequence across the middle using six beautifully composed illustration panels, left to right, no extra agents:
"01 Supervisor" with "Route the question"
"02 Planner" with "Define the steps"
"03 Retrieval" with "Find source passages"
"04 Tools" with "Run safe computations"
"05 Execution" with "Write with evidence"
"06 Critic" with "Check the answer"
Main arrows 01 → 02 → 03 → 04 → 05 → 06.
Above pipeline, a small entry card "User question" into Supervisor, and small exit card "Answer + citations" reached from Critic only after approval.
Below retrieval, show a coherent miniature document pipeline, exact labels "Upload" → "Chunk" → "Embed" → "Store"; use a paper, stacked text strips, floating vector points, and a database. Connect Store upward into Retrieval.
Below execution and critic, a clear curved return arrow from Critic to Execution labeled "One revision maximum".
At bottom, three well-separated supporting bands with exact labels:
"app/orchestrator.py — controls the sequence"
"app/llm.py — Gemini through EURI"
"app/store.py — evidence, memory and traces"
At top right small wordmark "relay."
Bottom tiny but readable note: "Retrieval and tools may be skipped when unnecessary. Empty evidence leads to an honest limitation."
Constraints: strictly 16:9 landscape, impeccable spelling, huge legible labels, correct stage order, no arrows suggesting all agents must always call the LLM, no claim of completed live validation, no fake charts or metrics, no watermark, no unrelated text. Professional lecture-ready visual hierarchy, not a dense wall of text.
```
