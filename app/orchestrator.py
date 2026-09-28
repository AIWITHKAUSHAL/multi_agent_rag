"""Control agent handoffs, bounded revisions, task concurrency, and durable traces."""

import asyncio
import logging
import time

from app.agents import (
    ExecutionAgent,
    PlanningAgent,
    ReflectionAgent,
    RetrievalAgent,
    SupervisorAgent,
    ToolAgent,
)
from app.llm import ProviderError
from app.store import now

log = logging.getLogger("agentic_rag")


class Orchestrator:
    """Run six specialist agents against shared state and persist their outcomes.

    A semaphore admits two executing runs while a session set prevents overlapping
    turns in one conversation. These controls apply only to this server process.
    """

    def __init__(self, store, llm, retriever):
        """Bind service dependencies and initialize the process-local task controls."""
        self.store, self.llm, self.retriever = store, llm, retriever
        self.active_sessions = set()
        self.capacity = asyncio.Semaphore(2)
        self.tasks = set()

    def start(self, request):
        """Reserve a session, persist a queued run, and schedule its background task.

        Return the run ID immediately. Reject a second active turn in the same
        session or an eleventh admitted session with ValueError for the API to
        translate into a conflict response.
        """
        if request.session_id in self.active_sessions:
            raise ValueError("This conversation already has an active run. Wait for it to finish.")
        if len(self.active_sessions) >= 10:
            raise ValueError("The classroom queue is full. Please retry shortly.")
        self.active_sessions.add(request.session_id)
        rid = self.store.create_run(request.session_id, request.query.strip())
        task = asyncio.create_task(self.run(rid, request))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return rid

    def emit(self, rid, agent, status, **details):
        """Persist a full trace event and log only its non-content execution metadata."""
        event = {"timestamp": now(), "agent": agent, "status": status, **details}
        self.store.event(rid, event)
        # Console logs deliberately omit document text, prompts and provider credentials.
        log.info(
            "run=%s agent=%s status=%s duration_ms=%s", rid, agent, status, details.get("duration_ms", "-")
        )

    async def invoke(self, rid, agent, state):
        """Call one agent with shared state and emit start/outcome timing events.

        Agent return values become trace details; the agent updates shared state
        itself. Exceptions emit a failed-agent event and propagate to the run's
        outer error handler rather than continuing with incomplete state.
        """
        self.emit(rid, agent.name, "running", reason=f"Running {agent.name} agent.")
        start = time.monotonic()
        try:
            details = await agent.run(state, self.llm, self.retriever)
        except Exception:
            self.emit(rid, agent.name, "failed", reason="Agent failed; see the run error.")
            raise
        self.emit(
            rid,
            agent.name,
            "skipped" if details.get("skipped") else "completed",
            duration_ms=round((time.monotonic() - start) * 1000),
            details=details,
        )

    async def run(self, rid, request):
        """Execute the ordered pipeline and at most one execution/critique revision.

        Load conversation history, invoke all six stages, and revisit only execution
        and reflection if the first critique fails. Persist the approved answer or
        a safe refusal plus its evidence, tools, and verdict. Handle failures and
        cancellation explicitly, and always release the active-session reservation.
        """
        start = time.monotonic()
        try:
            async with self.capacity:
                self.store.update_run(rid, "running")
                state = {
                    **request.model_dump(),
                    "history": self.store.history(request.session_id),
                    "documents": [{"id": d["id"], "name": d["name"]} for d in self.store.documents()],
                }
                execution, reflection = ExecutionAgent(), ReflectionAgent()
                for agent in [
                    SupervisorAgent(),
                    PlanningAgent(),
                    RetrievalAgent(),
                    ToolAgent(),
                    execution,
                    reflection,
                ]:
                    await self.invoke(rid, agent, state)
                revised = False
                if not state["critique"]["approved"]:
                    revised = True
                    self.emit(rid, "reflection", "revision", reason="Critic requested one bounded revision.")
                    state["feedback"] = {"draft": state["answer"], "critique": state["critique"]}
                    await self.invoke(rid, execution, state)
                    await self.invoke(rid, reflection, state)
                approved = state["critique"]["approved"]
                result = {
                    "answer": state["answer"]
                    if approved
                    else "I couldn't produce a sufficiently supported answer after review. Please refine the question or provide more evidence.",
                    "sources": state["sources"],
                    "tools": state["tools"],
                    "route": state["route"],
                    "plan": state["plan"],
                    "critique": state["critique"],
                    "revised": revised,
                    "model": self.llm.settings.euri_model,
                    "duration_ms": round((time.monotonic() - start) * 1000),
                }
                self.store.save_turn(request.session_id, request.query, result["answer"], rid)
                self.emit(
                    rid,
                    "final",
                    "completed" if approved else "needs_review",
                    reason="Final response is available.",
                )
                self.store.update_run(rid, "completed" if approved else "needs_review", result)
        except asyncio.CancelledError:
            self.store.update_run(rid, "failed", {"error": "Server stopped during this run. Please retry."})
            raise
        except Exception as exc:
            message = (
                str(exc)
                if isinstance(exc, (ProviderError, ValueError))
                else "Unexpected application error. See server logs and retry."
            )
            log.error("run=%s failed error_type=%s", rid, type(exc).__name__)
            self.emit(rid, "system", "failed", reason=message)
            self.store.update_run(rid, "failed", {"error": message})
        finally:
            self.active_sessions.discard(request.session_id)

    async def close(self):
        """Cancel and await outstanding tasks so interrupted runs are marked failed."""
        for task in list(self.tasks):
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
