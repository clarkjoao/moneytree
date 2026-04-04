import os
from pathlib import Path
from fastapi import APIRouter, HTTPException
from analyzer.metrics import _months_with_data, compute_month
from transaction_store import load_month_transactions

router = APIRouter()
ROOT = Path(__file__).resolve().parents[2]
PROCESSED_ROOT = ROOT / "data" / "processed"

@router.get("/months")
def get_months():
    return {"months": _months_with_data(PROCESSED_ROOT)}

@router.get("/metrics/{mes}")
def get_metrics(mes: str):
    month_dir = PROCESSED_ROOT / mes
    path = month_dir / f"metrics_{mes}.json"
    if not path.exists():
        # Fallback to computing on the fly if not exists
        try:
            metrics = compute_month(mes, project_root=ROOT)
            return metrics.model_dump()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    # Return pre-computed json
    import json
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

@router.get("/transactions/{mes}")
def get_transactions(mes: str):
    if not mes:
        raise HTTPException(status_code=400, detail="Mês inválido")
    transactions = load_month_transactions(PROCESSED_ROOT, mes)
    return [t.model_dump(mode="json") for t in transactions]
