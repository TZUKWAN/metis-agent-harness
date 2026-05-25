from metis.artifacts.store import ArtifactStore
from metis.artifacts.validators import checksum_matches, extension_matches, no_placeholder, non_empty
from metis.state.sqlite_store import SQLiteStateStore


def test_artifact_validators_detect_placeholder(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    session_id = state.create_session("s1")
    artifact_path = tmp_path / "report.md"
    artifact_path.write_text("TODO: 待补充", encoding="utf-8")
    artifact = ArtifactStore(state).register_artifact(
        session_id=session_id,
        path=artifact_path,
        artifact_type="markdown",
    )

    assert non_empty(artifact).passed is True
    assert extension_matches(artifact, ".md").passed is True
    assert checksum_matches(artifact).passed is True
    assert no_placeholder(artifact).passed is False
