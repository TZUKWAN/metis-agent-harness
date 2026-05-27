from fastapi.testclient import TestClient

from metis.app.manifest import AgentAppManifest
from metis.app.web import create_app
from metis.evidence.ledger import EvidenceLedger
from metis.runtime.response import AgentRunResult, ToolResult
from metis.state.sqlite_store import SQLiteStateStore


def test_web_app_exposes_rebrandable_config():
    manifest = AgentAppManifest(
        name="Acme Analyst",
        subtitle="Decision Agent",
        description="Acme internal decision agent",
        workspace=".",
        model="glm-4.7-flash",
        profile="small",
        icon_text="A",
    )
    client = TestClient(create_app(manifest))

    response = client.get("/api/config")

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Acme Analyst"
    assert payload["subtitle"] == "Decision Agent"
    assert payload["icon_text"] == "A"


def test_web_app_exposes_runtime_status(monkeypatch):
    monkeypatch.setenv("METIS_API_KEY", "test-key")
    monkeypatch.setenv("METIS_BASE_URL", "http://localhost:8000")
    manifest = AgentAppManifest(
        name="Acme Analyst",
        workspace=".",
        model="glm-4.7-flash",
        allowed_tool_permissions="read_only",
    )
    client = TestClient(create_app(manifest))

    response = client.get("/api/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["manifest"]["name"] == "Acme Analyst"
    assert payload["provider_capabilities"]["model"] == "glm-4.7-flash"
    assert payload["allowed_tool_permissions"] == ["read_only"]
    assert "read_file" in payload["tools"]


def test_web_app_exposes_session_detail():
    client = TestClient(create_app(AgentAppManifest(name="Acme Analyst", model="glm-4.7-flash")))
    client.app.state.sessions["s1"] = {
        "title": "A task",
        "model": "glm-4.7-flash",
        "messages": [{"role": "user", "content": "hello"}],
        "tool_calls": [{"name": "read_file"}],
        "evidence": [{"id": "e1"}],
    }

    list_response = client.get("/api/sessions")
    detail_response = client.get("/api/sessions/s1")

    assert list_response.status_code == 200
    assert list_response.json()["sessions"][0]["message_count"] == 1
    assert list_response.json()["sessions"][0]["tool_call_count"] == 1
    assert list_response.json()["sessions"][0]["evidence_count"] == 1
    assert detail_response.status_code == 200
    assert detail_response.json()["messages"] == [{"role": "user", "content": "hello"}]


def test_web_recorded_session_includes_tool_results_and_evidence(monkeypatch):
    async def fake_turn(message, *, manifest, workspace=None, max_turns=12, **kwargs):
        return AgentRunResult(
            status="final",
            final_text="done",
            tool_results=[
                ToolResult(
                    tool_name="run_test",
                    content="passed",
                    metadata={"evidence_refs": ["e1"]},
                )
            ],
            trace_events=[{"name": "tool.result"}],
        )

    monkeypatch.setattr("metis.app.web.run_agent_turn", fake_turn)
    client = TestClient(create_app(AgentAppManifest(name="Acme Analyst", model="glm-4.7-flash")))

    response = client.post("/api/chat", json={"session_id": "s1", "message": "run tests"})
    detail = client.get("/api/sessions/s1").json()

    assert response.status_code == 200
    assert detail["tool_calls"][0]["name"] == "run_test"
    assert detail["evidence"] == [{"id": "e1", "source": "run_test", "status": "ok"}]
    assert detail["trace_events"] == [{"name": "tool.result"}]


def test_web_app_reads_persisted_sessions_from_state_db(tmp_path):
    state_db = tmp_path / "state.db"
    state = SQLiteStateStore(state_db)
    state.create_session("s1")
    state.append_message("s1", "user", "persisted task")
    state.record_tool_call("s1", "read_file", {"path": "README.md"}, result="ok", status="ok")
    EvidenceLedger(state).record_claim(
        session_id="s1",
        claim="Read README",
        source_type="tool_output",
        source_ref="README.md",
        evidence_id="e1",
    )
    manifest = AgentAppManifest(name="Acme Analyst", workspace=str(tmp_path), state_db_path="state.db")
    client = TestClient(create_app(manifest))

    list_response = client.get("/api/sessions")
    detail_response = client.get("/api/sessions/s1")

    assert list_response.status_code == 200
    assert list_response.json()["sessions"][0]["id"] == "s1"
    assert list_response.json()["sessions"][0]["message_count"] == 1
    assert list_response.json()["sessions"][0]["tool_call_count"] == 1
    assert list_response.json()["sessions"][0]["evidence_count"] == 1
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["messages"][0]["content"] == "persisted task"
    assert detail["tool_calls"][0]["tool_name"] == "read_file"
    assert detail["evidence"][0]["id"] == "e1"


def test_web_app_serves_shell_html():
    client = TestClient(create_app(AgentAppManifest()))

    response = client.get("/")

    assert response.status_code == 200
    assert "brandName" in response.text
    assert "/static/app.js" in response.text
    assert "鈽" not in response.text
    assert "鉃" not in response.text
