"""Expose the classroom UI, upload/query APIs, and persisted live event streams."""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.config import Settings
from app.llm import LLM, ProviderError
from app.orchestrator import Orchestrator
from app.retrieval import Embedder, Retriever
from app.schemas import QueryRequest
from app.store import Store

STATIC = Path(__file__).parent / "static"


def create_app(settings=None, llm=None, embedder=None):
    """Build the FastAPI app and connect its provider, store, retriever, and engine.

    Optional dependencies support isolated tests; omitted dependencies use real
    EURI generation and local embeddings. Create one orchestrator per application
    instance and run one Uvicorn worker because task coordination is in-process.
    """
    settings = settings or Settings()
    store = Store(settings.data_dir / "classroom.db")
    provider = llm or LLM(settings)
    retriever = Retriever(settings, store, embedder or Embedder(settings))
    engine = Orchestrator(store, provider, retriever)
    upload_lock = asyncio.Lock()

    @asynccontextmanager
    async def lifespan(app):
        """Recover interrupted runs at startup and release background work at shutdown."""
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
        store.recover_runs()
        yield
        await engine.close()
        await provider.close()

    app = FastAPI(title="Agentic RAG Classroom", version="1.0.0", lifespan=lifespan)
    app.state.store, app.state.engine = store, engine
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/", include_in_schema=False)
    def home():
        """Serve the classroom HTML shell, which loads its CSS and JavaScript assets."""
        return FileResponse(STATIC / "index.html")

    @app.get("/architecture", include_in_schema=False)
    def architecture():
        """Serve the standalone code explorer with same-origin access to run events."""
        return FileResponse(STATIC / "architecture_visualizer.html")

    @app.get("/api/health")
    def health():
        """Report local readiness and configuration without contacting EURI or exposing secrets."""
        return {
            "status": "ok",
            "provider": "EURI",
            "model": settings.euri_model,
            "configured": settings.configured,
            "embedding_model": settings.embedding_model,
            "embedding_ready": getattr(retriever.embedder, "model", None) is not None,
            "documents": len(store.documents()),
            "mode": "live",
            "min_similarity": settings.min_similarity,
        }

    @app.post("/api/provider/check")
    async def provider_check():
        """Make a small live EURI request and return model/usage metadata on success."""
        try:
            _, usage = await provider.complete(
                "Reply with the word connected.", {"request": "Connection check"}
            )
            return {"connected": True, **usage}
        except ProviderError as exc:
            raise HTTPException(503, str(exc)) from exc

    @app.get("/api/documents")
    def documents():
        """List the shared classroom document library and ingestion metadata."""
        return store.documents()

    @app.post("/api/documents", status_code=201)
    async def upload(file: UploadFile = File(...)):
        """Validate an upload and run blocking ingestion in a worker thread.

        Serialize library mutations, enforce upload/document limits, and close
        the uploaded file even after failure. Convert expected extraction errors
        to HTTP 400 and embedding initialization failures to a safe HTTP 503.
        """
        try:
            content = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
            if len(content) > settings.max_upload_mb * 1024 * 1024:
                raise HTTPException(413, f"Upload limit is {settings.max_upload_mb} MB.")
            async with upload_lock:
                if len(store.documents()) >= 100:
                    raise HTTPException(
                        409, "Classroom library limit is 100 documents. Remove unused documents first."
                    )
                return await asyncio.to_thread(retriever.ingest, file.filename or "upload", content)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:
            logging.getLogger("agentic_rag").error("Upload failed: %s", type(exc).__name__)
            raise HTTPException(
                503,
                "Embedding initialization or ingestion failed. Check network/model download and server configuration.",
            ) from exc
        finally:
            await file.close()

    @app.get("/api/documents/{doc_id}/chunks")
    def chunks(doc_id: str):
        """Return one document's ordered chunks, or HTTP 404 if it is unavailable."""
        data = store.document_chunks(doc_id)
        if not data:
            raise HTTPException(404, "Document not found.")
        return data

    @app.delete("/api/documents/{doc_id}")
    async def delete(doc_id: str):
        """Remove a document and its vectors only when no query run is active."""
        async with upload_lock:
            if engine.active_sessions:
                raise HTTPException(409, "Wait for active runs before deleting evidence.")
            if not store.delete_document(doc_id):
                raise HTTPException(404, "Document not found.")
        return {"deleted": True}

    @app.post("/api/sessions", status_code=201)
    def session():
        """Create a conversation whose messages remain separate from other sessions."""
        return {"id": store.create_session()}

    @app.get("/api/sessions/{sid}/messages")
    def history(sid: str):
        """Return up to 200 stored messages for a known conversation."""
        if not store.session_exists(sid):
            raise HTTPException(404, "Conversation not found.")
        return store.history(sid, limit=200)

    @app.post("/api/runs", status_code=202)
    async def query(request: QueryRequest):
        """Validate request scope and enqueue a query, returning HTTP 202 with its ID.

        Reject blank questions, absent credentials, unknown sessions/documents,
        and session/queue conflicts before allowing the orchestrator to start.
        Read the final answer separately through the run or event endpoints.
        """
        if not request.query.strip():
            raise HTTPException(422, "Question cannot be blank.")
        if not settings.configured:
            raise HTTPException(
                503, "Set EURI_API_KEY in .env and restart the server before asking questions."
            )
        if not store.session_exists(request.session_id):
            raise HTTPException(404, "Conversation not found. Start a new conversation.")
        known = {d["id"] for d in store.documents()}
        if set(request.document_ids) - known:
            raise HTTPException(404, "A selected document no longer exists. Refresh your document library.")
        try:
            return {"id": engine.start(request)}
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/api/runs/{rid}")
    def run(rid: str):
        """Return a persisted run's status, final result, and complete trace."""
        data = store.get_run(rid)
        if not data:
            raise HTTPException(404, "Run not found.")
        return data

    @app.get("/api/runs/{rid}/events")
    async def events(rid: str, request: Request, after: int = 0):
        """Replay persisted agent events and stream new events until the run finishes.

        Resume after the greater of ``after`` and Last-Event-ID. The stream sends
        trace events, heartbeat comments, then a done event containing the final
        run. This is agent-event streaming, not token-by-token model generation.
        """
        if not store.get_run(rid):
            raise HTTPException(404, "Run not found.")
        try:
            cursor = max(after, int(request.headers.get("last-event-id", "0")))
        except ValueError:
            raise HTTPException(400, "Invalid event cursor.") from None

        async def stream():
            """Yield SSE frames while advancing the cursor and checking disconnection."""
            nonlocal cursor
            while not await request.is_disconnected():
                for event in store.events(rid, cursor):
                    cursor = event["id"]
                    yield f"id: {cursor}\nevent: trace\ndata: {json.dumps(event)}\n\n"
                run = store.get_run(rid)
                if run["status"] not in {"queued", "running"}:
                    yield f"event: done\ndata: {json.dumps(run)}\n\n"
                    break
                yield ": heartbeat\n\n"
                await asyncio.sleep(0.4)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app
