"""Build exact 16:9 SVG teaching diagrams from the application's verified call paths."""

from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "visuals"


class Board:
    """Compose a fixed-size, accessible SVG with shared typography and routing helpers."""

    def __init__(self, title, subtitle, number, dark=False):
        """Initialize a 1920×1080 artboard with a consistent teaching-slide header."""
        self.dark = dark
        self.ink = "#edf4fa" if dark else "#172e38"
        self.muted = "#9aafc2" if dark else "#617783"
        self.line = "#344c62" if dark else "#cfdad9"
        self.paper = "#152d43" if dark else "#ffffff"
        bg = "#0a1b2b" if dark else "#f5f6f1"
        self.parts = [
            '<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" '
            'viewBox="0 0 1920 1080" role="img" aria-labelledby="title description">',
            f'<title id="title">{escape(title)}</title><desc id="description">{escape(subtitle)}</desc>',
            '<defs><pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse">'
            f'<circle cx="1" cy="1" r="1" fill="{self.line}" opacity=".4"/></pattern>'
            '<marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto-start-reverse">'
            '<path d="M1 1L8 5L1 9" fill="none" stroke="context-stroke" stroke-width="1.7"/>'
            "</marker></defs>",
            f'<rect width="1920" height="1080" fill="{bg}"/>',
            '<rect width="1920" height="1080" fill="url(#grid)" opacity=".38"/>',
        ]
        self.text(64, 54, "RELAY  /  CODE EXPLAINED", 16, "#6baf9d", weight=700, spacing=3)
        self.text(1856, 54, f"{number} / 04", 16, self.muted, anchor="end", mono=True)
        self.text(64, 118, title, 48, weight=700)
        self.text(64, 160, subtitle, 21, self.muted)
        self.rect(64, 1018, 1792, 1, self.line, radius=0)
        self.text(
            64, 1052, "ACTUAL CODE PATHS  ·  ARROWS SHOW CALLS OR DATA HANDOFFS", 14, self.muted, spacing=1
        )
        self.text(1856, 1052, "1920 × 1080  /  16:9", 15, self.muted, anchor="end", mono=True)

    def text(self, x, y, value, size=20, color=None, weight=400, mono=False, anchor="start", spacing=0):
        """Add escaped SVG text using a locally available sans-serif or monospace font."""
        font = "Menlo,Consolas,monospace" if mono else "Arial,Helvetica,sans-serif"
        self.parts.append(
            f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" '
            f'fill="{color or self.ink}" font-weight="{weight}" text-anchor="{anchor}" '
            f'letter-spacing="{spacing}">{escape(value)}</text>'
        )

    def rect(self, x, y, w, h, fill=None, stroke=None, radius=16):
        """Add a rounded panel, rule, or accent strip."""
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" '
            f'fill="{fill or self.paper}" stroke="{stroke or "none"}"/>'
        )

    def arrow(self, points, color="#69ad9b", dashed=False):
        """Draw a directed polyline along explicitly chosen, non-overlapping waypoints."""
        coordinates = " ".join(f"{x},{y}" for x, y in points)
        self.parts.append(
            f'<polyline points="{coordinates}" fill="none" stroke="{color}" stroke-width="2.5" '
            f'stroke-linejoin="round" marker-end="url(#arrow)" '
            f'stroke-dasharray="{"7 6" if dashed else "none"}"/>'
        )

    def card(self, x, y, w, h, label, title, lines, accent="#69ad9b", title_size=27):
        """Lay out a file/function card with an accent label and concise body lines."""
        self.rect(x, y, w, h, stroke=self.line)
        self.rect(x + 1, y + 19, 4, h - 38, accent, radius=2)
        self.text(x + 24, y + 32, label, 14, accent, weight=700, spacing=1.4)
        self.text(x + 24, y + 69, title, title_size, weight=700)
        for i, line in enumerate(lines):
            self.text(x + 24, y + 103 + 27 * i, line, 18, self.muted)

    def save(self, name):
        """Write an editable SVG source alongside the presentation PNG exports."""
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / name).write_text("\n".join(self.parts + ["</svg>"]), encoding="utf-8")


def file_map():
    """Show the primary runtime chain and the services each agent actually calls."""
    b = Board(
        "What calls what?",
        "Read left to right for a question; follow the branches for evidence, tools, and model calls.",
        "02",
        dark=True,
    )
    b.card(
        64,
        220,
        310,
        156,
        "01 / BROWSER",
        "static/app.js",
        ["chat-form → POST /api/runs", "index.html + style.css = UI"],
    )
    b.card(
        454,
        220,
        340,
        156,
        "02 / HTTP BOUNDARY",
        "app/main.py",
        ["query(QueryRequest)", "validate → engine.start()"],
    )
    b.card(
        874,
        220,
        360,
        156,
        "03 / CONTROLLER",
        "app/orchestrator.py",
        ["start() → run() → invoke()", "owns order, state, and revision"],
        title_size=25,
    )
    b.card(
        1314,
        220,
        542,
        156,
        "04 / SPECIALISTS",
        "app/agents.py",
        ["Supervisor → Planning → Retrieval", "Tool → Execution → Reflection"],
    )
    for x1, x2 in [(374, 454), (794, 874), (1234, 1314)]:
        b.arrow([(x1 + 5, 295), (x2 - 9, 295)])
    b.arrow([(1435, 376), (1435, 429), (254, 429), (254, 553)])
    b.text(66, 419, "RetrievalAgent.run()", 16, "#69ad9b", mono=True)
    b.arrow([(1590, 376), (1590, 471), (684, 471), (684, 553)], "#dfa377")
    b.text(532, 460, "ToolAgent.run()", 16, "#dfa377", mono=True)
    b.arrow([(1750, 376), (1750, 512), (1115, 512), (1115, 553)], "#94b6f0")
    b.text(907, 501, "LLM-backed agent decisions", 16, "#94b6f0")
    b.card(
        64,
        560,
        380,
        194,
        "EVIDENCE SERVICE",
        "app/retrieval.py",
        ["Retriever.search()", "Embedder.encode(query=True)", "then Store.search()"],
    )
    b.card(
        494,
        560,
        380,
        194,
        "ALLOWLISTED COMPUTATION",
        "app/tools.py",
        ["run_tool(ToolCall)", "calculate() / clock / dates", "return result OR tool error"],
        accent="#dfa377",
    )
    b.card(
        924,
        560,
        380,
        194,
        "LIVE MODEL ADAPTER",
        "app/llm.py",
        ["structured() → complete()", "AsyncOpenAI → EURI / Gemini", "validated JSON + token usage"],
        accent="#94b6f0",
    )
    b.card(
        1354,
        560,
        502,
        194,
        "PERSISTENCE",
        "app/store.py",
        [
            "Called by main, orchestrator, retrieval",
            "SQLite: chunks, vectors, turns, runs",
            "event() → events() → main.py SSE",
        ],
    )
    b.arrow([(254, 754), (254, 800), (1605, 800), (1605, 761)])
    b.text(560, 788, "retrieval.py delegates vector persistence and cosine ranking to Store", 17, "#69ad9b")
    b.card(
        64,
        850,
        535,
        139,
        "CONFIGURATION",
        "app/config.py",
        ["main.create_app() loads Settings from .env"],
        title_size=24,
    )
    b.card(
        627,
        850,
        593,
        139,
        "CONTRACTS",
        "app/schemas.py",
        ["FastAPI validates requests; llm validates decisions"],
        title_size=24,
    )
    b.card(
        1248,
        850,
        608,
        139,
        "RETURN PATH",
        "SSE → static/app.js",
        ["main.events() → watchRun() → completeRun()"],
        title_size=24,
    )
    b.save("02-file-call-map.svg")


def ingestion():
    """Trace upload processing and show how stored chunks become answer evidence."""
    b = Board(
        "How a document becomes evidence",
        "The upload path builds the library once. The question path searches the same persistent vectors.",
        "03",
    )
    xs = [64, 524, 984, 1444]
    b.card(
        xs[0],
        224,
        412,
        188,
        "01 / SELECT FILE",
        "static/app.js",
        ["uploadFiles(files)", "FormData → POST /api/documents", "PDF, UTF-8 TXT, or Markdown"],
    )
    b.card(
        xs[1],
        224,
        412,
        188,
        "02 / VALIDATE UPLOAD",
        "app/main.py",
        ["upload(file)", "size / library limits + upload lock", "to_thread(retriever.ingest, ...)"],
    )
    b.card(
        xs[2],
        224,
        412,
        188,
        "03 / EXTRACT CONTENT",
        "app/retrieval.py",
        ["Retriever.ingest(name, bytes)", "extract_pages() → page text", "PDF page numbers are preserved"],
    )
    b.card(
        xs[3],
        224,
        412,
        188,
        "04 / SPLIT TEXT",
        "app/retrieval.py",
        ["chunk_pages(pages, 900, 150)", "overlapping character windows", "page + offsets + original slices"],
    )
    for x1, x2 in zip(xs, xs[1:]):
        b.arrow([(x1 + 419, 312), (x2 - 8, 312)], "#3d8274")
    b.arrow([(1650, 412), (1650, 462), (270, 462), (270, 508)], "#3d8274")
    b.text(715, 450, "fingerprint content + model + chunk settings; reuse duplicates", 19, "#3d8274")
    b.card(
        xs[0],
        516,
        412,
        190,
        "05 / VECTORIZE NEW TEXT",
        "app/retrieval.py",
        ["Embedder.encode(chunk_texts)", "local FastEmbed model on CPU", "normalized float32 vectors"],
    )
    b.card(
        xs[1],
        516,
        412,
        190,
        "06 / ATOMIC WRITE",
        "app/store.py",
        ["Store.insert_document(...)", "document metadata + all chunks", "vectors stored as SQLite BLOBs"],
    )
    b.card(
        xs[2],
        516,
        412,
        190,
        "07 / PERSISTENT LIBRARY",
        "data/classroom.db",
        ["document ID / name / digest", "page / position / start / end", "embedding model + timestamp"],
    )
    b.card(
        xs[3],
        516,
        412,
        190,
        "08 / REPORT TO THE UI",
        "main.py → app.js",
        [
            "document metadata + created flag",
            "loadDocuments() refreshes library",
            "Inspect chunks shows stored text",
        ],
    )
    for x1, x2 in zip(xs, xs[1:]):
        b.arrow([(x1 + 419, 605), (x2 - 8, 605)], "#3d8274")
    b.rect(64, 763, 1792, 221, "#e8eee7", stroke="#c9d7c8")
    b.text(90, 799, "WHEN A QUESTION NEEDS DOCUMENTS", 15, "#3d8274", weight=700, spacing=2)
    steps = [
        (90, "agents.py", "RetrievalAgent.run()"),
        (534, "retrieval.py", "search() → encode(query=True)"),
        (978, "store.py", "search(): cosine → Top-K"),
        (1422, "agents.py", "ExecutionAgent.run()"),
    ]
    for x, title, subtitle in steps:
        b.text(x, 853, title, 27, weight=700)
        b.text(x, 889, subtitle, 17, b.muted, mono=True)
    for x in [476, 920, 1364]:
        b.arrow([(x, 850), (x + 37, 850)], "#3d8274")
    b.text(
        90,
        949,
        "Search applies document scope and minimum similarity. Selected passages receive [S1], [S2], … citation IDs.",
        21,
    )
    b.save("03-document-ingestion.svg")


def question_flow():
    """Explain ordered agent calls, shared-state outputs, and the bounded critic loop."""
    b = Board(
        "One question, every handoff",
        "Control flow stays in orchestrator.py. Each specialist in agents.py updates the same run state.",
        "04",
    )
    b.rect(64, 202, 1792, 81, "#e7edf2", stroke="#d3dce3")
    b.text(88, 236, "ENTRY", 14, "#56758e", weight=700, spacing=2)
    b.text(88, 263, "app.js → main.query() → Orchestrator.start() → run() → invoke(agent)", 24, weight=700)
    b.text(1257, 251, "Store.history() loads prior turns", 19, "#56758e")
    positions = [(64, 320), (690, 320), (1316, 320), (64, 579), (690, 579), (1316, 579)]
    content = [
        (
            "01 / SUPERVISOR",
            "SupervisorAgent.run()",
            ["llm.structured(..., Route)", "history + question → standalone intent", "writes state['route']"],
        ),
        (
            "02 / PLANNING",
            "PlanningAgent.run()",
            ["llm.structured(..., Plan)", "route → steps + retrieval query", "writes state['plan']"],
        ),
        (
            "03 / RETRIEVAL",
            "RetrievalAgent.run()",
            [
                "retrieval.search() → store.search()",
                "Top-K passages OR explicit skip",
                "writes state['sources']",
            ],
        ),
        (
            "04 / TOOLS",
            "ToolAgent.run()",
            [
                "llm.structured(..., ToolSelection)",
                "tools.run_tool() → result OR error",
                "writes state['tools']",
            ],
        ),
        (
            "05 / EXECUTION",
            "ExecutionAgent.run()",
            [
                "llm.complete(evidence + tools)",
                "empty retrieval → honest abstention",
                "writes state['answer']",
            ],
        ),
        (
            "06 / REFLECTION",
            "ReflectionAgent.run()",
            [
                "citation_issues() + llm.structured()",
                "review evidence, citations, tool results",
                "writes state['critique']",
            ],
        ),
    ]
    for (x, y), (label, title, lines) in zip(positions, content, strict=True):
        b.card(x, y, 540, 188, label, title, lines, title_size=27)
    for y in [412, 671]:
        b.arrow([(611, y), (682, y)], "#3d8274")
        b.arrow([(1237, y), (1308, y)], "#3d8274")
    b.arrow([(1586, 508), (1586, 546), (334, 546), (334, 571)], "#3d8274")
    b.text(685, 537, "orchestrator invokes the next specialist", 17, "#3d8274")
    b.arrow([(1586, 767), (1586, 822), (960, 822), (960, 775)], "#c86d46")
    b.text(992, 809, "Rejected? One revision: Execution → Reflection", 18, "#b65f3c")
    b.rect(64, 865, 1120, 126, "#e8eee7", stroke="#c9d7c8")
    b.text(88, 899, "FINALIZE / orchestrator.py → store.py → main.py → app.js", 18, "#3d8274", weight=700)
    b.text(88, 936, "Approved: answer + citations. Rejected again: safe refusal with needs_review.", 21)
    b.text(88, 966, "save_turn() + update_run() → events() SSE → completeRun()", 19, b.muted, mono=True)
    b.rect(1212, 865, 644, 126, "#e7edf2", stroke="#d3dce3")
    b.text(1236, 900, "TRACE AT EVERY STAGE", 16, "#56758e", weight=700, spacing=1)
    b.text(1236, 936, "invoke() → emit() → Store.event()", 22, weight=700)
    b.text(1236, 967, "Running / completed / skipped / failed + timing", 18, b.muted)
    b.save("04-question-lifecycle.svg")


def main():
    """Write the three editable companion diagrams without changing application behavior."""
    file_map()
    ingestion()
    question_flow()
    print(f"Wrote 3 SVG diagrams to {OUT}")


if __name__ == "__main__":
    main()
