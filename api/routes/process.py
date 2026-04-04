import asyncio
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, HTTPException
import main as cli_main

router = APIRouter()
ROOT = Path(__file__).resolve().parents[2]

process_jobs = {}

def bg_process(job_id: str, mes: str):
    try:
        process_jobs[job_id] = {"status": "running"}
        cli_main.classify_command(mes, ROOT / "config", use_llm=True)
        cli_main.analyze_command(mes, only_metrics=False)
        process_jobs[job_id] = {"status": "done"}
    except Exception as e:
        process_jobs[job_id] = {"status": "error", "message": str(e)}

@router.post("/process/{mes}")
async def start_process(mes: str, background_tasks: BackgroundTasks):
    job_id = f"job_process_{mes}"
    if process_jobs.get(job_id, {}).get("status") == "running":
        return {"job_id": job_id, "status": "already_running"}
        
    process_jobs[job_id] = {"status": "pending"}
    background_tasks.add_task(bg_process, job_id, mes)
    return {"job_id": job_id, "status": "started"}

@router.get("/process/status/{job_id}")
def get_process_status(job_id: str):
    if job_id not in process_jobs:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    return process_jobs[job_id]
