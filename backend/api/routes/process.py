from __future__ import annotations

import threading
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.pipeline.jobs import job_store
from backend.pipeline.orchestrator import (
    CLASSIFY_ONLY_STEPS,
    PIPELINE_STEPS,
    run_classify_pipeline,
    run_full_pipeline,
)

router = APIRouter()


class ProcessRequest(BaseModel):
    use_llm: bool = True


@router.post("/process/upload")
def start_upload_pipeline(body: ProcessRequest) -> dict:
    """
    Inicia o pipeline completo: parse + classify + analyze.
    Usado pelo fluxo de upload quando o frontend quer processar tudo de uma vez.
    """
    job_id = f"upload_{int(time.time())}"
    job_store.create(job_id, mes="detectando...", steps=PIPELINE_STEPS)

    thread = threading.Thread(
        target=run_full_pipeline,
        args=(job_id,),
        kwargs={"use_llm": body.use_llm},
        daemon=True,
    )
    thread.start()

    return {"job_id": job_id, "status": "started"}


@router.post("/process/{mes}")
def start_classify_pipeline(mes: str, body: ProcessRequest) -> dict:
    """
    Inicia classify + analyze para um mês já parseado.
    Usado quando os JSONs já existem e o usuário quer re-classificar ou rodar o pipeline.
    """
    processed_root = Path(__file__).resolve().parents[2] / "data" / "processed"
    month_dir = processed_root / mes
    if not (month_dir / "fatura.json").exists() and not (month_dir / "extrato.json").exists():
        raise HTTPException(
            status_code=404,
            detail=f"Nenhum dado encontrado para {mes}. Faça o upload e parse primeiro.",
        )

    job_id = f"classify_{mes}_{int(time.time())}"
    job_store.create(job_id, mes=mes, steps=CLASSIFY_ONLY_STEPS)

    thread = threading.Thread(
        target=run_classify_pipeline,
        args=(job_id, mes),
        kwargs={"use_llm": body.use_llm},
        daemon=True,
    )
    thread.start()

    return {"job_id": job_id, "status": "started", "mes": mes}


@router.get("/process/status/{job_id}")
def get_job_status(job_id: str) -> dict:
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' não encontrado.")
    return job.to_dict()


@router.get("/process/jobs")
def list_jobs() -> list[dict]:
    return [job.to_dict() for job in job_store.all()]
