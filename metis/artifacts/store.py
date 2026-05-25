"""Artifact registration and lookup."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ArtifactRecord:
    id: str
    session_id: str
    type: str
    path: str
    checksum: str
    status: str = "created"
    metadata: dict[str, Any] = field(default_factory=dict)


class ArtifactStore:
    def __init__(self, state) -> None:
        self.state = state

    def register_artifact(
        self,
        *,
        session_id: str,
        path: str | Path,
        artifact_type: str,
        status: str = "created",
        metadata: dict[str, Any] | None = None,
        artifact_id: str | None = None,
    ) -> ArtifactRecord:
        resolved = Path(path).resolve()
        if not resolved.exists() or not resolved.is_file():
            raise FileNotFoundError(str(resolved))
        artifact_id = artifact_id or uuid.uuid4().hex[:12]
        checksum = self.compute_checksum(resolved)
        with self.state._connect() as conn:
            conn.execute(
                """
                INSERT INTO artifacts (id, session_id, type, path, checksum, status, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact_id,
                    session_id,
                    artifact_type,
                    str(resolved),
                    checksum,
                    status,
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )
        return ArtifactRecord(artifact_id, session_id, artifact_type, str(resolved), checksum, status, metadata or {})

    def get_artifact(self, artifact_id: str) -> ArtifactRecord | None:
        with self.state._connect() as conn:
            row = conn.execute("SELECT * FROM artifacts WHERE id=?", (artifact_id,)).fetchone()
        return self._row_to_record(row) if row else None

    def list_artifacts(self, session_id: str) -> list[ArtifactRecord]:
        with self.state._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM artifacts WHERE session_id=? ORDER BY created_at, id",
                (session_id,),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    @staticmethod
    def compute_checksum(path: str | Path) -> str:
        digest = hashlib.sha256()
        with Path(path).open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _row_to_record(row) -> ArtifactRecord:
        return ArtifactRecord(
            id=row["id"],
            session_id=row["session_id"],
            type=row["type"],
            path=row["path"],
            checksum=row["checksum"],
            status=row["status"],
            metadata=json.loads(row["metadata_json"]),
        )
