"""Evidence ledger for claims and source references."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from metis.evidence.schema import EvidenceStrength, SOURCE_TYPES


@dataclass(frozen=True)
class EvidenceRecord:
    id: str
    session_id: str
    claim: str
    source_type: str
    source_ref: str
    strength: str = EvidenceStrength.MEDIUM.value
    metadata: dict[str, Any] = field(default_factory=dict)


class EvidenceLedger:
    def __init__(self, state) -> None:
        self.state = state

    def record_claim(
        self,
        *,
        session_id: str,
        claim: str,
        source_type: str,
        source_ref: str,
        strength: str = EvidenceStrength.MEDIUM.value,
        metadata: dict[str, Any] | None = None,
        evidence_id: str | None = None,
    ) -> EvidenceRecord:
        if source_type not in SOURCE_TYPES:
            raise ValueError(f"Unsupported evidence source_type: {source_type}")
        evidence_id = evidence_id or uuid.uuid4().hex[:12]
        with self.state._connect() as conn:
            conn.execute(
                """
                INSERT INTO evidence (id, session_id, claim, source_type, source_ref, strength, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evidence_id,
                    session_id,
                    claim,
                    source_type,
                    source_ref,
                    strength,
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )
        return EvidenceRecord(evidence_id, session_id, claim, source_type, source_ref, strength, metadata or {})

    def list_evidence(self, session_id: str) -> list[EvidenceRecord]:
        with self.state._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM evidence WHERE session_id=? ORDER BY created_at, id",
                (session_id,),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def find_by_source(self, session_id: str, source_type: str, source_ref: str | None = None) -> list[EvidenceRecord]:
        query = "SELECT * FROM evidence WHERE session_id=? AND source_type=?"
        params: list[Any] = [session_id, source_type]
        if source_ref is not None:
            query += " AND source_ref=?"
            params.append(source_ref)
        query += " ORDER BY created_at, id"
        with self.state._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_record(row) for row in rows]

    def summarize_for_prompt(self, session_id: str, *, max_items: int = 20) -> str:
        records = self.list_evidence(session_id)[:max_items]
        return "\n".join(f"- [{record.source_type}] {record.claim} ({record.source_ref})" for record in records)

    @staticmethod
    def _row_to_record(row) -> EvidenceRecord:
        return EvidenceRecord(
            id=row["id"],
            session_id=row["session_id"],
            claim=row["claim"],
            source_type=row["source_type"],
            source_ref=row["source_ref"],
            strength=row["strength"],
            metadata=json.loads(row["metadata_json"]),
        )
