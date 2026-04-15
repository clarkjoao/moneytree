from __future__ import annotations

from backend.pipeline.jobs import JobStore
from backend.pipeline.orchestrator import _on_classify_progress


def test_job_to_dict_includes_kind_current_step_and_counters() -> None:
    store = JobStore()
    store.create(
        "job_1",
        kind="pipeline",
        mes="2026-04",
        steps=[
            ("parse", "Extraindo transações dos PDFs"),
            ("classify", "Classificando transações"),
        ],
    )
    store.update_step("job_1", "parse", status="done")
    store.update_step("job_1", "classify", status="running")
    store.update_counters(
        "job_1",
        files_total=2,
        files_processed=1,
        transactions_total=80,
        transactions_extracted=80,
        transactions_classified=55,
        transactions_pending=25,
    )

    payload = store.get("job_1").to_dict()  # type: ignore[union-attr]

    assert payload["kind"] == "pipeline"
    assert payload["current_step"] == {
        "name": "classify",
        "label": "Classificando transações",
        "status": "running",
    }
    assert payload["counters"]["files_total"] == 2
    assert payload["counters"]["transactions_pending"] == 25


def test_on_classify_progress_updates_job_store() -> None:
    store = JobStore()
    original = __import__("backend.pipeline.orchestrator", fromlist=["job_store"]).job_store
    orchestrator = __import__("backend.pipeline.orchestrator", fromlist=["job_store"])
    orchestrator.job_store = store
    try:
        store.create(
            "job_2",
            kind="classify",
            mes="2026-04",
            steps=[("classify", "Classificando transações")],
        )
        store.update_step("job_2", "classify", status="running")

        _on_classify_progress(
            "job_2",
            {
                "phase": "llm_running",
                "total": 80,
                "classified": 60,
                "pending": 20,
                "llm_processed": 40,
                "llm_total": 50,
                "lotes_llm_falhos": 1,
            },
        )

        payload = store.get("job_2").to_dict()  # type: ignore[union-attr]
        assert payload["counters"]["transactions_total"] == 80
        assert payload["counters"]["transactions_classified"] == 60
        assert payload["counters"]["transactions_pending"] == 20
        assert payload["counters"]["llm_batches_failed"] == 1
        assert payload["steps"][0]["detail"] == "LLM 40/50 · 60 classificadas · 20 pendentes"
    finally:
        orchestrator.job_store = original
