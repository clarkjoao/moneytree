import re
import shutil
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

router = APIRouter()
ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_ROOT = ROOT / "data" / "processed"

_SUPPORTED_BANKS = {"itau"}


def _normalize_bank(value: str) -> str:
    bank = value.strip().lower()
    if bank not in _SUPPORTED_BANKS:
        raise HTTPException(status_code=400, detail=f"Banco inválido: {value}")
    return bank


def _normalize_mes(value: str) -> str:
    match = re.fullmatch(r"(20\d{2})-(\d{2})", value.strip())
    if not match:
        raise HTTPException(status_code=400, detail="Mês inválido (use YYYY-MM)")
    return f"{match.group(1)}-{match.group(2)}"


def _safe_stem(filename: str, fallback: str) -> str:
    stem = Path(filename).stem if filename else fallback
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", stem).strip("_")
    return cleaned or fallback


def _target_filename(bank: str, mes: str, original_filename: str, index: int) -> str:
    base_hint = _safe_stem(original_filename, f"arquivo_{index + 1}")
    if bank == "itau":
        return f"FATURA_MASTERCARD_{mes}_{base_hint}.pdf"
    return f"{bank}_{mes}_{base_hint}.pdf"


@router.post("/upload")
async def upload_files(
    files: list[UploadFile] = File(...),
    mes: str = Form(...),
    bank: str = Form(...),
) -> dict:
    """
    Salva os PDFs em data/raw/. Não dispara processamento.
    O frontend deve chamar POST /api/process/upload após o upload.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    normalized_mes = _normalize_mes(mes)
    normalized_bank = _normalize_bank(bank)

    for index, file in enumerate(files):
        if not file.filename:
            continue
        candidate_name = _target_filename(normalized_bank, normalized_mes, file.filename, index)
        path = RAW_DIR / candidate_name
        suffix = 1
        while path.exists():
            path = RAW_DIR / candidate_name.replace(".pdf", f"_{suffix}.pdf")
            suffix += 1
        with path.open("wb") as buf:
            shutil.copyfileobj(file.file, buf)
        saved.append(path.name)

    return {
        "status": "uploaded",
        "files": saved,
        "mes": normalized_mes,
        "bank": normalized_bank,
    }


@router.get("/parse-status/{mes}")
def parse_status(mes: str) -> dict:
    """Returns {"ready": true} once fatura.json or extrato.json exists for the given month."""
    if not re.match(r"^\d{4}-\d{2}$", mes):
        raise HTTPException(status_code=400, detail="Mês inválido (use YYYY-MM)")
    month_dir = PROCESSED_ROOT / mes
    ready = (month_dir / "fatura.json").exists() or (month_dir / "extrato.json").exists()
    return {"ready": ready, "mes": mes}
