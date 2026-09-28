import time

from fastapi.testclient import TestClient

from app.main import create_app


def test_api_upload_run_stream_and_inspect(settings, doubles):
    with TestClient(create_app(settings, doubles.llm, doubles.embedder)) as client:
        assert client.get("/").status_code == 200
        assert client.get("/static/app.js").status_code == 200
        assert client.get("/docs").status_code == 200
        assert client.get("/api/health").json()["mode"] == "live"
        doc = client.post("/api/documents", files={"file": ("fee.md", b"Course fee is INR 12000.")})
        assert doc.status_code == 201
        doc_id = doc.json()["id"]
        assert client.get(f"/api/documents/{doc_id}/chunks").json()[0]["page"] == 1
        sid = client.post("/api/sessions").json()["id"]
        response = client.post("/api/runs", json={"session_id": sid, "query": "What is the fee?"})
        assert response.status_code == 202
        rid = response.json()["id"]
        for _ in range(100):
            run = client.get(f"/api/runs/{rid}").json()
            if run["status"] not in {"queued", "running"}:
                break
            time.sleep(0.01)
        assert run["status"] == "completed"
        events = client.get(f"/api/runs/{rid}/events").text
        assert "event: trace" in events and "event: done" in events
        last_event = run["events"][-1]["id"]
        assert (
            "event: trace"
            not in client.get(f"/api/runs/{rid}/events", headers={"Last-Event-ID": str(last_event)}).text
        )
        assert len(client.get(f"/api/sessions/{sid}/messages").json()) == 2
        assert client.delete(f"/api/documents/{doc_id}").status_code == 200


def test_api_validates_failures(settings, doubles):
    with TestClient(create_app(settings, doubles.llm, doubles.embedder)) as client:
        sid = client.post("/api/sessions").json()["id"]
        for query in ["", "   ", "x" * 4001]:
            assert client.post("/api/runs", json={"session_id": sid, "query": query}).status_code == 422
        assert (
            client.post("/api/runs", json={"session_id": sid, "query": "Hi", "top_k": 9}).status_code == 422
        )
        assert client.post("/api/runs", json={"session_id": "0" * 32, "query": "Hi"}).status_code == 404
        assert (
            client.post(
                "/api/runs", json={"session_id": sid, "query": "Hi", "document_ids": ["missing"]}
            ).status_code
            == 404
        )
        assert client.post("/api/documents", files={"file": ("bad.exe", b"data")}).status_code == 400
        assert client.post("/api/documents", files={"file": ("empty.txt", b"")}).status_code == 400
        assert (
            client.post(
                "/api/documents",
                files={"file": ("large.txt", b"a" * (settings.max_upload_mb * 1024 * 1024 + 1))},
            ).status_code
            == 413
        )
        assert client.get("/api/runs/missing").status_code == 404
        assert client.get("/api/runs/missing/events").status_code == 404
        assert client.delete("/api/documents/missing").status_code == 404


def test_missing_key_is_explicit(settings, doubles):
    from pydantic import SecretStr

    settings.euri_api_key = SecretStr("")
    with TestClient(create_app(settings, doubles.llm, doubles.embedder)) as client:
        assert not client.get("/api/health").json()["configured"]
        sid = client.post("/api/sessions").json()["id"]
        response = client.post("/api/runs", json={"session_id": sid, "query": "Hello"})
        assert response.status_code == 503 and "EURI_API_KEY" in response.json()["detail"]
