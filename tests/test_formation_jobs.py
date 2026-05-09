from pathlib import Path

from memisalluneed.formation_jobs import FormationJob, FormationJobStore
from memisalluneed.formation_jobs import FormationWorker
from memisalluneed.schema import create_memory_item
from memisalluneed.session import SessionTurn
from memisalluneed.store import MemoryStore


def make_turn(turn_id: str = "turn-1") -> SessionTurn:
    return SessionTurn(
        id=turn_id,
        user_message="remember this",
        assistant_message="stored",
        recalled_memory_ids=["memory-1"],
        created_at="2026-05-09T00:00:00+00:00",
    )


def test_formation_job_round_trips():
    job = FormationJob.new(session_id="session-1", turn=make_turn())

    loaded = FormationJob.from_dict(job.to_dict())

    assert loaded.id == job.id
    assert loaded.session_id == "session-1"
    assert loaded.turn.id == "turn-1"
    assert loaded.status == "pending"
    assert loaded.written_memory_ids == []
    assert loaded.error is None


def test_job_store_appends_and_lists_newest_first(tmp_path: Path):
    store = FormationJobStore(tmp_path / "formation_jobs.json")
    older = FormationJob.new(session_id="session-1", turn=make_turn("turn-1"))
    newer = FormationJob.new(session_id="session-1", turn=make_turn("turn-2"))

    store.append(older)
    store.append(newer)

    assert [job.turn.id for job in store.list()] == ["turn-2", "turn-1"]


def test_job_store_updates_status_and_error(tmp_path: Path):
    store = FormationJobStore(tmp_path / "formation_jobs.json")
    job = FormationJob.new(session_id="session-1", turn=make_turn())
    store.append(job)

    store.mark_running(job.id)
    assert store.get(job.id).status == "running"

    store.mark_failed(job.id, "The read operation timed out")
    failed = store.get(job.id)
    assert failed.status == "failed"
    assert failed.error == "The read operation timed out"

    store.reset_failed_to_pending(job.id)
    reset = store.get(job.id)
    assert reset.status == "pending"
    assert reset.error is None


def test_job_store_marks_written_with_memory_ids(tmp_path: Path):
    store = FormationJobStore(tmp_path / "formation_jobs.json")
    job = FormationJob.new(session_id="session-1", turn=make_turn())
    store.append(job)

    store.mark_written(job.id, ["memory-1", "memory-2"])

    written = store.get(job.id)
    assert written.status == "written"
    assert written.written_memory_ids == ["memory-1", "memory-2"]
    assert written.error is None


def test_job_store_recovers_running_jobs_as_pending(tmp_path: Path):
    store = FormationJobStore(tmp_path / "formation_jobs.json")
    job = FormationJob.new(session_id="session-1", turn=make_turn())
    store.append(job)
    store.mark_running(job.id)

    recovered = store.recover_interrupted_jobs()

    assert [job.id for job in recovered] == [job.id]
    assert store.get(job.id).status == "pending"


class FakeFormationModel:
    def __init__(self, response: str):
        self.response = response

    def complete(self, messages):
        return self.response


class FailingFormationModel:
    def complete(self, messages):
        raise RuntimeError("The read operation timed out")


def test_worker_processes_job_and_marks_written(tmp_path: Path):
    job_store = FormationJobStore(tmp_path / "formation_jobs.json")
    memory_store = MemoryStore(tmp_path / "memory.db")
    memory_store.init()
    recalled = create_memory_item("Existing recalled memory.")
    memory_store.add(recalled)
    turn = make_turn("turn-1")
    job = FormationJob.new(session_id="session-1", turn=turn)
    job_store.append(job)
    model = FakeFormationModel(
        """
{"memories":[{"type":"experience","content":"formed async memory","state":"success","confidence":0.8,"metadata":{"source":"chat_session","formation_kind":"chat_qa","session_id":"session-1","turn_id":"turn-1","recalled_memory_ids":["memory-1"],"used_memory_ids":["memory-1"]}}]}
""".strip()
    )
    worker = FormationWorker(
        job_store=job_store,
        memory_store=memory_store,
        formation_model_factory=lambda: model,
    )

    worker.process_one(job)

    updated = job_store.get(job.id)
    assert updated.status == "written"
    assert len(updated.written_memory_ids) == 1
    assert memory_store.all()[0].content == "formed async memory"


def test_worker_marks_failed_on_exception(tmp_path: Path):
    job_store = FormationJobStore(tmp_path / "formation_jobs.json")
    memory_store = MemoryStore(tmp_path / "memory.db")
    memory_store.init()
    job = FormationJob.new(session_id="session-1", turn=make_turn())
    job_store.append(job)
    worker = FormationWorker(
        job_store=job_store,
        memory_store=memory_store,
        formation_model_factory=lambda: FailingFormationModel(),
    )

    worker.process_one(job)

    updated = job_store.get(job.id)
    assert updated.status == "failed"
    assert updated.error == "The read operation timed out"
    assert memory_store.all() == []


def test_worker_start_enqueues_pending_and_recovers_running(tmp_path: Path):
    job_store = FormationJobStore(tmp_path / "formation_jobs.json")
    memory_store = MemoryStore(tmp_path / "memory.db")
    memory_store.init()
    pending = FormationJob.new(session_id="session-1", turn=make_turn("turn-pending"))
    running = FormationJob.new(session_id="session-1", turn=make_turn("turn-running"))
    job_store.append(pending)
    job_store.append(running)
    job_store.mark_running(running.id)
    worker = FormationWorker(
        job_store=job_store,
        memory_store=memory_store,
        formation_model_factory=lambda: FakeFormationModel('{"memories":[]}'),
    )

    worker.enqueue_startup_jobs()

    assert worker.queue_size() == 2
    assert job_store.get(running.id).status == "pending"
