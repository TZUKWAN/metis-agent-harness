from metis.artifacts.store import ArtifactStore
from metis.state.sqlite_store import SQLiteStateStore


def test_artifact_store_registers_file_and_checksum(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    session_id = state.create_session("s1")
    artifact_path = tmp_path / "report.md"
    artifact_path.write_text("real report", encoding="utf-8")
    store = ArtifactStore(state)

    record = store.register_artifact(session_id=session_id, path=artifact_path, artifact_type="markdown")

    assert record.checksum == ArtifactStore.compute_checksum(artifact_path)
    assert store.get_artifact(record.id) == record
    assert store.list_artifacts(session_id) == [record]
