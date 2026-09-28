import json

import httpx
import pytest
from openai import AsyncOpenAI

from app.llm import LLM, ProviderError
from app.schemas import Route


def completion(content, finish_reason="stop"):
    return {
        "id": "test",
        "object": "chat.completion",
        "created": 0,
        "model": "gemini-test",
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": finish_reason}
        ],
        "usage": {"prompt_tokens": 3, "completion_tokens": 5, "total_tokens": 8},
    }


def provider_with_transport(settings, handler):
    llm = LLM(settings)
    original = llm.client
    llm.client = AsyncOpenAI(
        api_key="unit-test-placeholder",
        base_url=settings.euri_base_url,
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    return llm, original


async def test_sdk_sends_expected_euri_payload(settings):
    def handler(request):
        assert str(request.url) == "https://api.euron.one/api/v1/euri/chat/completions"
        payload = json.loads(request.content)
        assert payload["model"] == "gemini-3.5-flash-lite"
        assert payload["messages"][0]["role"] == "system"
        return httpx.Response(200, json=completion("Connected"))

    llm, original = provider_with_transport(settings, handler)
    try:
        answer, usage = await llm.complete("system", {"query": "hello"})
        assert answer == "Connected" and usage["completion_tokens"] == 5
    finally:
        await llm.close()
        await original.close()


@pytest.mark.parametrize(
    "code,pattern", [(401, "key"), (403, "access"), (404, "model"), (429, "quota"), (500, "500")]
)
async def test_provider_errors_do_not_leak_response_or_key(settings, code, pattern):
    llm, original = provider_with_transport(
        settings, lambda _: httpx.Response(code, json={"error": {"message": "SECRET"}})
    )
    try:
        with pytest.raises(ProviderError, match=pattern) as error:
            await llm.complete("system", {})
        assert "SECRET" not in str(error.value)
        assert "unit-test-placeholder" not in str(error.value)
    finally:
        await llm.close()
        await original.close()


async def test_structured_output_repairs_once(settings):
    calls = []
    route = {
        "intent": "direct",
        "needs_retrieval": False,
        "needs_tools": False,
        "standalone_query": "hello",
        "reason": "Greeting",
    }

    def handler(request):
        calls.append(request)
        if len(calls) == 2:
            repair = json.loads(json.loads(request.content)["messages"][1]["content"])
            assert repair["original_request"] == {"query": "hello"}
            assert repair["previous_response"] == "invalid"
            assert "json_invalid" in repair["validation_errors"]
        return httpx.Response(
            200, json=completion("invalid" if len(calls) == 1 else f"```json\n{json.dumps(route)}\n```")
        )

    llm, original = provider_with_transport(settings, handler)
    try:
        value, usage = await llm.structured("route", {"query": "hello"}, Route)
        assert value.intent == "direct" and len(usage["calls"]) == 2
    finally:
        await llm.close()
        await original.close()


async def test_invalid_json_fails_after_two_attempts(settings):
    llm, original = provider_with_transport(
        settings, lambda _: httpx.Response(200, json=completion("not JSON"))
    )
    try:
        with pytest.raises(ProviderError, match="twice"):
            await llm.structured("route", {}, Route)
    finally:
        await llm.close()
        await original.close()


async def test_schema_repair_receives_field_errors_and_keeps_original_query(settings):
    calls = []
    valid = {
        "intent": "direct",
        "needs_retrieval": False,
        "needs_tools": False,
        "standalone_query": "hello",
        "reason": "Greeting",
    }

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(200, json=completion(json.dumps({**valid, "intent": "greeting"})))
        repair = json.loads(json.loads(request.content)["messages"][1]["content"])
        assert "intent: literal_error" in repair["validation_errors"]
        assert json.loads(repair["previous_response"])["intent"] == "greeting"
        assert repair["original_request"]["query"] == "hello"
        return httpx.Response(200, json=completion(f"```JSON\n{json.dumps(valid)}\n```"))

    llm, original = provider_with_transport(settings, handler)
    try:
        route, usage = await llm.structured("route", {"query": "hello"}, Route)
        assert route.intent == "direct" and len(usage["calls"]) == 2
    finally:
        await llm.close()
        await original.close()


async def test_failed_schema_validation_reports_contract_without_response_data(settings, caplog):
    secret = "SENSITIVE-MODEL-TEXT"
    invalid = {"intent": secret, secret: secret}
    llm, original = provider_with_transport(
        settings, lambda _: httpx.Response(200, json=completion(json.dumps(invalid)))
    )
    try:
        with pytest.raises(ProviderError, match="Route JSON twice") as error:
            await llm.structured("route", {}, Route)
        assert "intent: literal_error" in str(error.value)
        assert "standalone_query: missing" in str(error.value)
        assert secret not in str(error.value)
        assert secret not in caplog.text
        assert "<unknown field>: extra_forbidden" in caplog.text
    finally:
        await llm.close()
        await original.close()


@pytest.mark.parametrize("content,finish", [("", "stop"), ("partial", "length")])
async def test_empty_and_truncated_output_rejected(settings, content, finish):
    llm, original = provider_with_transport(
        settings, lambda _: httpx.Response(200, json=completion(content, finish))
    )
    try:
        with pytest.raises(ProviderError, match="empty or truncated"):
            await llm.complete("system", {})
    finally:
        await llm.close()
        await original.close()
