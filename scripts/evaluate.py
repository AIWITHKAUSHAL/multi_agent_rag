"""Run the 36-case suite against a real, running app. Never supplies a fake provider."""

import argparse
import json
import math
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def check_result(case, run):
    """Return failed assertions for a live run's answer, citations, tools, and trace.

    Compare case expectations with actual persisted outputs. Text patterns and
    citation membership are smoke checks, not a proof of semantic grounding.
    """
    errors = []
    result = run.get("result") or {}
    answer = result.get("answer", "")
    if run["status"] != "completed":
        errors.append(f"Run status {run['status']}: {result.get('error', '')}")
    for pattern in case.get("patterns", []):
        if not re.search(pattern, answer, re.I):
            errors.append(f"Answer missing expected pattern: {pattern}")
    for pattern in case.get("forbidden_patterns", []):
        if re.search(pattern, answer, re.I):
            errors.append(f"Forbidden answer pattern matched: {pattern}")
    valid_ids = {s["citation"] for s in result.get("sources", [])}
    citations = set(re.findall(r"\[(S\d+)\]", answer))
    if citations - valid_ids:
        errors.append("Answer invented a citation ID")
    if case.get("citations") and not citations:
        errors.append("Expected document citations")
    if "retrieval" in case and result.get("route", {}).get("needs_retrieval") != case["retrieval"]:
        errors.append("Unexpected retrieval routing")
    if case.get("tool"):
        outputs = [t for t in result.get("tools", []) if t["name"] == case["tool"]]
        if not outputs:
            errors.append(f"Expected tool {case['tool']} was not called")
        elif case.get("tool_error"):
            if not any(not t["ok"] for t in outputs):
                errors.append("Expected tool error was not reported")
        elif not any(t["ok"] for t in outputs):
            errors.append("Required tool did not succeed")
        if "numeric_result" in case and not any(
            t.get("ok")
            and isinstance(t.get("result"), (int, float))
            and math.isclose(t["result"], case["numeric_result"], abs_tol=0.01)
            for t in outputs
        ):
            errors.append(f"Expected numeric tool result {case['numeric_result']}")
    invoked = {e["agent"] for e in run.get("events", []) if e["status"] == "running"}
    if invoked != {"supervisor", "planning", "retrieval", "tool", "execution", "reflection"}:
        errors.append("Incomplete six-agent trace")
    return errors


def write_report(path, report):
    """Save full JSON evidence and a sibling Markdown summary, including blocked runs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    rows = [
        "# Live EURI evaluation",
        "",
        f"UTC: {report['timestamp']}",
        f"Status: {report['status']}",
        f"Model: {report.get('model', 'unconfirmed')}",
        "",
        "These are live application checks. Pattern checks are not a substitute for human review of grounding.",
        "",
    ]
    if report.get("error"):
        rows += [f"Preflight error: {report['error']}", "No query results are claimed.", ""]
    rows += ["| Case | Category | Result |", "|---|---|---|"]
    rows += [f"| {r['id']} | {r['category']} | {r['status']} |" for r in report["results"]]
    if report["results"]:
        rows += [
            "",
            f"Counts: {dict(Counter(r['status'] for r in report['results']))}",
            "",
            "Full answers, assertions, tool outputs and traces are in the accompanying JSON.",
            "Review those artifacts for document entailment, useful explanations and safe failures before submitting.",
        ]
    path.with_suffix(".md").write_text("\n".join(rows) + "\n", encoding="utf-8")


def main():
    """Run live preflight and categorized queries; return 0/pass, 1/fail, or 2/blocked.

    Upload the teaching corpus, isolate unrelated cases in separate conversations,
    preserve follow-up groups, and checkpoint results after every case. Credentials
    and real server/provider access are required; no test doubles are introduced.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path, default=ROOT / "reports/live-results.json")
    parser.add_argument(
        "--category", choices=["direct", "document", "tool", "multi_step", "follow_up", "failure"]
    )
    args = parser.parse_args()
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "running",
        "mode": "live",
        "results": [],
    }
    cases = json.loads((ROOT / "evaluation/queries.json").read_text())
    if args.category:
        cases = [c for c in cases if c["category"] == args.category]
    sessions = {}
    with httpx.Client(base_url=args.base_url, timeout=180) as client:
        try:
            health_response = client.get("/api/health")
            health_response.raise_for_status()
            health = health_response.json()
            report["model"] = health["model"]
            if not health["configured"]:
                raise RuntimeError("EURI_API_KEY is missing. Configure .env and restart the app.")
            check = client.post("/api/provider/check")
            check.raise_for_status()
            report["provider_check"] = check.json()
            for name in ("course-handbook.md", "project-requirements.md"):
                with (ROOT / "examples" / name).open("rb") as file:
                    upload = client.post("/api/documents", files={"file": (name, file)})
                    upload.raise_for_status()
        except (httpx.HTTPError, RuntimeError) as exc:
            report.update(status="blocked", error=str(exc))
            write_report(args.output, report)
            print(f"Live evaluation blocked: {exc}")
            return 2
        for case in cases:
            result = {"id": case["id"], "category": case["category"], "query": case["query"]}
            try:
                group = case.get("conversation", case["id"])
                if group not in sessions:
                    session = client.post("/api/sessions")
                    session.raise_for_status()
                    sessions[group] = session.json()["id"]
                response = client.post(
                    "/api/runs",
                    json={
                        "session_id": sessions[group],
                        "query": case["query"],
                        "top_k": case.get("top_k", 6),
                    },
                )
                if "http_status" in case:
                    errors = (
                        []
                        if response.status_code == case["http_status"]
                        else [f"Expected HTTP {case['http_status']}, got {response.status_code}"]
                    )
                    result["response"] = response.json()
                else:
                    response.raise_for_status()
                    rid = response.json()["id"]
                    deadline = time.monotonic() + 900
                    while True:
                        response = client.get(f"/api/runs/{rid}")
                        response.raise_for_status()
                        run = response.json()
                        if run["status"] not in {"queued", "running"}:
                            break
                        if time.monotonic() > deadline:
                            raise RuntimeError(
                                "Run exceeded 15 minutes; inspect the server before continuing."
                            )
                        time.sleep(0.5)
                    result["run"] = run
                    errors = check_result(case, run)
                result.update(status="pass" if not errors else "fail", errors=errors)
            except (httpx.HTTPError, RuntimeError) as exc:
                result.update(status="error", errors=[str(exc)])
            report["results"].append(result)
            print(f"{case['id']} {case['category']:12} {result['status']}", flush=True)
            write_report(args.output, report)
    report["status"] = "passed" if all(r["status"] == "pass" for r in report["results"]) else "failed"
    write_report(args.output, report)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
