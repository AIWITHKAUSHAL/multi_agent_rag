import asyncio

import pytest

from app.agents import citation_issues
from app.orchestrator import Orchestrator
from app.retrieval import Retriever
from app.schemas import QueryRequest
from app.store import Store
from tests.conftest import ScriptedLLM


async def execute(settings, embedder, llm, document=True):
    store = Store(settings.data_dir / "test.db")
    retriever = Retriever(settings, store, embedder)
    if document:
        retriever.ingest("fee.md", b"Course fee is INR 12000. GST is 18%.")
    engine = Orchestrator(store, llm, retriever)
    sid = store.create_session()
    request = QueryRequest(query="What is the course fee?", session_id=sid)
    rid = engine.start(request)
    await asyncio.gather(*engine.tasks)
    return store, engine, store.get_run(rid), sid


async def test_six_agents_order_citations_tools_history(settings, doubles):
    llm = ScriptedLLM(settings, tool=True)
    store, engine, run, sid = await execute(settings, doubles.embedder, llm)
    assert run["status"] == "completed"
    assert [e["agent"] for e in run["events"] if e["status"] == "running"] == [
        "supervisor",
        "planning",
        "retrieval",
        "tool",
        "execution",
        "reflection",
    ]
    assert run["result"]["tools"][0]["result"] == pytest.approx(14160)
    assert "[S1]" in run["result"]["answer"]
    assert len(store.history(sid)) == 2
    assert store.history(store.create_session()) == []
    rid = engine.start(QueryRequest(query="And what is its tax?", session_id=sid))
    await asyncio.gather(*engine.tasks)
    routes = [payload for name, payload in llm.prompts if name == "Route"]
    assert len(routes[1]["history"]) == 2
    assert store.get_run(rid)["status"] == "completed"


async def test_no_evidence_abstains(settings, doubles):
    _, _, run, _ = await execute(settings, doubles.embedder, doubles.llm, document=False)
    assert run["status"] == "completed"
    assert "cannot verify" in run["result"]["answer"]
    assert not run["result"]["sources"]
    assert not any(name == "complete" for name, _ in doubles.llm.prompts)


@pytest.mark.parametrize(
    "reject,status,revised", [(0, "completed", False), (1, "completed", True), (2, "needs_review", True)]
)
async def test_bounded_critique_loop(settings, doubles, reject, status, revised):
    llm = ScriptedLLM(settings, reject=reject)
    _, _, run, _ = await execute(settings, doubles.embedder, llm)
    assert run["status"] == status and run["result"]["revised"] == revised
    assert sum(e["agent"] == "execution" and e["status"] == "running" for e in run["events"]) <= 2
    if status == "needs_review":
        assert "couldn't produce" in run["result"]["answer"]


async def test_invalid_citation_cannot_pass_even_if_llm_approves(settings, doubles):
    _, _, run, _ = await execute(settings, doubles.embedder, ScriptedLLM(settings, invalid_citation=True))
    assert run["status"] == "needs_review"
    assert "S99" not in run["result"]["answer"]


async def test_direct_skips_retrieval_and_tool(settings, doubles):
    _, _, run, _ = await execute(settings, doubles.embedder, ScriptedLLM(settings, retrieval=False))
    assert {e["agent"] for e in run["events"] if e["status"] == "skipped"} == {"retrieval", "tool"}


async def test_same_session_is_serialized(settings, doubles):
    store = Store(settings.data_dir / "test.db")
    engine = Orchestrator(store, doubles.llm, Retriever(settings, store, doubles.embedder))
    sid = store.create_session()
    request = QueryRequest(query="fee", session_id=sid)
    engine.start(request)
    with pytest.raises(ValueError, match="active run"):
        engine.start(request)
    await asyncio.gather(*engine.tasks)
    assert sid not in engine.active_sessions


def test_restart_recovers_incomplete_runs(settings):
    store = Store(settings.data_dir / "test.db")
    rid = store.create_run(store.create_session(), "fee")
    store.recover_runs()
    assert store.get_run(rid)["status"] == "failed"


def test_citation_checks():
    assert citation_issues("Claim [S2]", [{"citation": "S1"}], True)
    assert not citation_issues("Claim [S1]", [{"citation": "S1"}], True)
