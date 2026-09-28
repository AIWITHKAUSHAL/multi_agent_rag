"""Test doubles are dependency-injected here only; the production app has no fake mode."""

from types import SimpleNamespace

import numpy as np
import pytest

from app.config import Settings
from app.schemas import Critique, Plan, Route, ToolSelection


class TestEmbedder:
    def encode(self, texts, query=False):
        vectors = []
        for text in texts:
            text = text.lower()
            values = np.array(
                [1 + text.count("fee") + text.count("12000"), text.count("refund"), text.count("session")],
                dtype=np.float32,
            )
            vectors.append(values / np.linalg.norm(values))
        return np.array(vectors)


class ScriptedLLM:
    def __init__(self, settings, *, retrieval=True, tool=False, reject=0, invalid_citation=False):
        self.settings = settings
        self.retrieval, self.tool, self.reject = retrieval, tool, reject
        self.invalid_citation = invalid_citation
        self.prompts = []

    async def structured(self, system, payload, schema):
        self.prompts.append((schema.__name__, payload))
        if schema is Route:
            value = Route(
                intent="document" if self.retrieval else "direct",
                needs_retrieval=self.retrieval,
                needs_tools=self.tool,
                standalone_query=payload["query"],
                reason="Test route",
            )
        elif schema is Plan:
            value = Plan(
                steps=["Retrieve fee", "Answer with evidence"],
                retrieval_query=payload["query"],
                success_criteria="Cite the fee",
            )
        elif schema is ToolSelection:
            value = ToolSelection(
                calls=[
                    {
                        "name": "calculator",
                        "arguments": {"expression": "12000*1.18"},
                        "reason": "Compute fee with GST",
                    }
                ],
                reason="Arithmetic required",
            )
        elif schema is Critique:
            approved = self.reject <= 0
            self.reject -= 1
            value = Critique(
                approved=approved, issues=[] if approved else ["Revise"], feedback="Check evidence"
            )
        return value, {"calls": [{"model": "TEST-DOUBLE", "prompt_tokens": 10, "completion_tokens": 10}]}

    async def complete(self, system, payload):
        self.prompts.append(("complete", payload))
        answer = "Fee: INR 12000 [S99]." if self.invalid_citation else "Fee: INR 12000 [S1]."
        if not self.retrieval:
            answer = "RAG retrieves evidence before generating an answer."
        return answer, {"model": "TEST-DOUBLE"}

    async def close(self):
        pass


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None,
        euri_api_key="unit-test-placeholder",
        data_dir=tmp_path,
        min_similarity=0.1,
        chunk_size=300,
        chunk_overlap=40,
    )


@pytest.fixture
def doubles(settings):
    return SimpleNamespace(llm=ScriptedLLM(settings), embedder=TestEmbedder())
