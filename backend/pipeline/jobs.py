from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Literal

StepStatus = Literal["pending", "running", "done", "skipped", "error"]
JobStatus = Literal["pending", "running", "done", "error"]
JobKind = Literal["extract", "classify", "pipeline"]


@dataclass
class StepResult:
    name: str
    label: str
    status: StepStatus = "pending"
    detail: str | None = None
    error: str | None = None
    started_at: float | None = None
    finished_at: float | None = None

    @property
    def duration_ms(self) -> int | None:
        if self.started_at and self.finished_at:
            return int((self.finished_at - self.started_at) * 1000)
        return None


@dataclass
class JobCounters:
    files_total: int | None = None
    files_processed: int | None = None
    transactions_total: int | None = None
    transactions_extracted: int | None = None
    transactions_classified: int | None = None
    transactions_pending: int | None = None
    transactions_review: int | None = None
    llm_batches_failed: int | None = None


@dataclass
class Job:
    id: str
    kind: JobKind
    mes: str
    status: JobStatus = "pending"
    steps: list[StepResult] = field(default_factory=list)
    counters: JobCounters = field(default_factory=JobCounters)
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    error: str | None = None

    def current_step(self) -> StepResult | None:
        running = next((step for step in self.steps if step.status == "running"), None)
        if running is not None:
            return running
        done = [step for step in self.steps if step.status == "done"]
        if done:
            return done[-1]
        return self.steps[0] if self.steps else None

    def to_dict(self) -> dict:
        current_step = self.current_step()
        return {
            "id": self.id,
            "kind": self.kind,
            "mes": self.mes,
            "status": self.status,
            "error": self.error,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "current_step": {
                "name": current_step.name,
                "label": current_step.label,
                "status": current_step.status,
            }
            if current_step
            else None,
            "counters": asdict(self.counters),
            "steps": [
                {
                    "name": step.name,
                    "label": step.label,
                    "status": step.status,
                    "detail": step.detail,
                    "error": step.error,
                    "duration_ms": step.duration_ms,
                }
                for step in self.steps
            ],
        }


class JobStore:
    """Thread-safe store de jobs em memória."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, job_id: str, kind: JobKind, mes: str, steps: list[tuple[str, str]]) -> Job:
        job = Job(
            id=job_id,
            kind=kind,
            mes=mes,
            steps=[StepResult(name=name, label=label) for name, label in steps],
        )
        with self._lock:
            self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def all(self) -> list[Job]:
        with self._lock:
            return list(self._jobs.values())

    def update_step(self, job_id: str, step_name: str, **kwargs: object) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            for step in job.steps:
                if step.name == step_name:
                    for key, value in kwargs.items():
                        setattr(step, key, value)
                    break

    def update_job(self, job_id: str, **kwargs: object) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            for key, value in kwargs.items():
                setattr(job, key, value)

    def update_counters(self, job_id: str, **kwargs: int | None) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            for key, value in kwargs.items():
                if hasattr(job.counters, key):
                    setattr(job.counters, key, value)

    def set_job_status(self, job_id: str, status: JobStatus, error: str | None = None) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job.status = status
            if error:
                job.error = error
            if status in ("done", "error"):
                job.finished_at = time.time()


job_store = JobStore()
