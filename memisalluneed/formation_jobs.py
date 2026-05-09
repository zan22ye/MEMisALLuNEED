from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from memisalluneed.schema import utc_now
from memisalluneed.session import SessionTurn

JOB_STATUSES = {"pending", "running", "written", "failed"}


@dataclass(frozen=True)
class FormationJob:
    id: str
    session_id: str
    turn: SessionTurn
    status: str
    written_memory_ids: list[str] = field(default_factory=list)
    error: str | None = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    @classmethod
    def new(cls, *, session_id: str, turn: SessionTurn) -> "FormationJob":
        now = utc_now()
        return cls(
            id=str(uuid4()),
            session_id=session_id,
            turn=turn,
            status="pending",
            created_at=now,
            updated_at=now,
        )

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "FormationJob":
        status = str(data["status"])
        if status not in JOB_STATUSES:
            raise ValueError(f"Invalid formation job status: {status}")
        turn = data["turn"]
        if not isinstance(turn, dict):
            raise ValueError("Formation job turn must be an object")
        return cls(
            id=str(data["id"]),
            session_id=str(data["session_id"]),
            turn=SessionTurn.from_dict(turn),
            status=status,
            written_memory_ids=[
                str(value) for value in data.get("written_memory_ids", [])
            ],
            error=None if data.get("error") is None else str(data.get("error")),
            created_at=str(data["created_at"]),
            updated_at=str(data["updated_at"]),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "turn": self.turn.to_dict(),
            "status": self.status,
            "written_memory_ids": list(self.written_memory_ids),
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class FormationJobStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, job: FormationJob) -> None:
        jobs = self._load()
        jobs.append(job)
        self._save(jobs)

    def list(self, *, limit: int | None = None) -> list[FormationJob]:
        jobs = sorted(self._load(), key=lambda job: job.created_at, reverse=True)
        if limit is not None:
            return jobs[:limit]
        return jobs

    def get(self, job_id: str) -> FormationJob:
        for job in self._load():
            if job.id == job_id:
                return job
        raise KeyError(f"Formation job not found: {job_id}")

    def mark_running(self, job_id: str) -> None:
        self._replace(job_id, status="running", error=None)

    def mark_written(self, job_id: str, memory_ids: list[str]) -> None:
        self._replace(
            job_id,
            status="written",
            written_memory_ids=list(memory_ids),
            error=None,
        )

    def mark_failed(self, job_id: str, error: str) -> None:
        self._replace(job_id, status="failed", error=error)

    def reset_failed_to_pending(self, job_id: str) -> FormationJob:
        job = self.get(job_id)
        if job.status != "failed":
            raise ValueError("Only failed formation jobs can be retried")
        self._replace(job_id, status="pending", error=None)
        return self.get(job_id)

    def recover_interrupted_jobs(self) -> list[FormationJob]:
        recovered: list[FormationJob] = []
        for job in self._load():
            if job.status == "running":
                self._replace(job.id, status="pending", error=None)
                recovered.append(self.get(job.id))
        return recovered

    def pending_jobs(self) -> list[FormationJob]:
        return [job for job in self._load() if job.status == "pending"]

    def _replace(self, job_id: str, **changes) -> None:
        jobs = []
        found = False
        for job in self._load():
            if job.id == job_id:
                data = job.to_dict()
                data.update(changes)
                data["updated_at"] = utc_now()
                job = FormationJob.from_dict(data)
                found = True
            jobs.append(job)
        if not found:
            raise KeyError(f"Formation job not found: {job_id}")
        self._save(jobs)

    def _load(self) -> list[FormationJob]:
        if not self.path.exists():
            return []
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("Formation job file must contain a list")
        return [FormationJob.from_dict(item) for item in data if isinstance(item, dict)]

    def _save(self, jobs: list[FormationJob]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                [job.to_dict() for job in jobs],
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
