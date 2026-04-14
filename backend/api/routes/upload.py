import re
import shutil
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from backend.cli import parse_command

router = APIRouter()
ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_ROOT = ROOT / "data" / "processed"


def _extract_mes_from_filename(filename: str) -> str | None:
    """Try to extract YYYY-MM from a filename like fatura_2026-03.pdf."""
    match = re.search(r'(\d{4})[-_](\d{2})', filename)
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    return None


@router.post("/upload")
async def upload_files(background_tasks: BackgroundTasks, files: list[UploadFile] = File(...)):
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    saved_files = []
    detected_mes: str | None = None

    for file in files:
        if file.filename:
            path = RAW_DIR / file.filename
            with path.open("wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            saved_files.append(file.filename)
            if detected_mes is None:
                detected_mes = _extract_mes_from_filename(file.filename)

    background_tasks.add_task(parse_command, RAW_DIR, False)

    return {"status": "processing_started", "files": saved_files, "mes": detected_mes}


@router.get("/parse-status/{mes}")
def parse_status(mes: str):
    """Returns {"ready": true} once fatura.json or extrato.json exists for the given month."""
    if not re.match(r"^\d{4}-\d{2}$", mes):
        raise HTTPException(status_code=400, detail="Mês inválido (use YYYY-MM)")
    month_dir = PROCESSED_ROOT / mes
    ready = (month_dir / "fatura.json").exists() or (month_dir / "extrato.json").exists()
    return {"ready": ready, "mes": mes}
