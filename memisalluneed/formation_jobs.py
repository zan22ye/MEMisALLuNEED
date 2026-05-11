from __future__ import annotations

import json
import queue
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from memisalluneed.file_io import write_json_atomic
from memisalluneed.formation import FormationService
from memisalluneed.models.base import ChatModel
from memisalluneed.schema import utc_now
from memisalluneed.session import SessionTurn
from memisalluneed.store import MemoryStore

JOB_STATUSES = {"pending", "running", "written", "failed"}


def _turn_already_formed(memory_store: MemoryStore, turn_id: str) -> bool:
    """Return True if a memory with matching chat_qa turn_id metadata exists."""
    for memory in memory_store.all():
        if (
            memory.metadata.get("source") == "chat_session"
            and memory.metadata.get("formation_kind") == "chat_qa"
            and memory.metadata.get("turn_id") == turn_id
        ):
            return True
    return False


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
        self._lock = threading.RLock()

    def append(self, job: FormationJob) -> None:
        with self._lock:
            jobs = self._load()
            jobs.append(job)
            self._save(jobs)

    def list(self, *, limit: int | None = None) -> list[FormationJob]:
        with self._lock:
            jobs = sorted(self._load(), key=lambda job: job.created_at, reverse=True)
            if limit is not None:
                return jobs[:limit]
            return jobs

    def get(self, job_id: str) -> FormationJob:
        with self._lock:
            for job in self._load():
                if job.id == job_id:
                    return job
            raise KeyError(f"Formation job not found: {job_id}")

    def mark_running(self, job_id: str) -> None:
        with self._lock:
            self._replace(job_id, status="running", error=None)

    def mark_written(self, job_id: str, memory_ids: list[str]) -> None:
        with self._lock:
            self._replace(
                job_id,
                status="written",
                written_memory_ids=list(memory_ids),
                error=None,
            )

    def mark_failed(self, job_id: str, error: str) -> None:
        with self._lock:
            self._replace(job_id, status="failed", error=error)

    def reset_failed_to_pending(self, job_id: str) -> FormationJob:
        with self._lock:
            job = self.get(job_id)
            if job.status != "failed":
                raise ValueError("Only failed formation jobs can be retried")
            self._replace(job_id, status="pending", error=None)
            return self.get(job_id)

    def recover_interrupted_jobs(self) -> list[FormationJob]:
        with self._lock:
            recovered: list[FormationJob] = []
            for job in self._load():
                if job.status == "running":
                    self._replace(job.id, status="pending", error=None)
                    recovered.append(self.get(job.id))
            return recovered

    def pending_jobs(self) -> list[FormationJob]:
        with self._lock:
            return [job for job in self._load() if job.status == "pending"]

    def _replace(self, job_id: str, **changes) -> None:
        with self._lock:
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
        write_json_atomic(self.path, [job.to_dict() for job in jobs])


class FormationWorker:
    def __init__(
        self,
        *,
        job_store: FormationJobStore,
        memory_store: MemoryStore,
        formation_model_factory: Callable[[], ChatModel],
    ) -> None:
        self.job_store = job_store
        self.memory_store = memory_store
        self.formation_model_factory = formation_model_factory
        self._queue: queue.Queue[str] = queue.Queue()
        self._thread: threading.Thread | None = None

    def enqueue(self, job: FormationJob) -> None:
        self._queue.put(job.id)

    def enqueue_startup_jobs(self) -> None:
        enqueued: set[str] = set()
        for job in self.job_store.recover_interrupted_jobs():
            self.enqueue(job)
            enqueued.add(job.id)
        for job in self.job_store.pending_jobs():
            if job.id in enqueued:
                continue
            self.enqueue(job)

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self.enqueue_startup_jobs()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def queue_size(self) -> int:
        return self._queue.qsize()

    def process_one(self, job: FormationJob) -> None:
        if _turn_already_formed(self.memory_store, job.turn.id):
            self.job_store.mark_written(job.id, [])
            return
        self.job_store.mark_running(job.id)
        try:
            model = self.formation_model_factory()
            formation = FormationService(model=model, store=self.memory_store)
            recalled_memories = [
                memory
                for memory_id in job.turn.recalled_memory_ids
                if (memory := self.memory_store.get(memory_id)) is not None
            ]
            written = formation.form_from_chat_qa_turn(
                session_id=job.session_id,
                turn=job.turn,
                recalled_memories=recalled_memories,
            )
            self.job_store.mark_written(job.id, [memory.id for memory in written])
        except Exception as error:
            self.job_store.mark_failed(job.id, str(error))

    def _run(self) -> None:
        while True:
            job_id = self._queue.get()
            try:
                job = self.job_store.get(job_id)
                if job.status == "pending":
                    self.process_one(job)
            finally:
                self._queue.task_done()
