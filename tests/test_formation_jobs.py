from pathlib import Path

from memisalluneed.formation_jobs import FormationJob, FormationJobStore
from memisalluneed.session import SessionTurn


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
