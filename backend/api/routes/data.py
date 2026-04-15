import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.analyzer.metrics import _months_with_data, compute_month
from backend.transaction_store import load_month_transactions

router = APIRouter()
ROOT = Path(__file__).resolve().parents[2]
PROCESSED_ROOT = ROOT / "data" / "processed"
CONFIG_ROOT = ROOT / "config"

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


@router.get("/taxonomy")
def get_taxonomy():
    path = CONFIG_ROOT / "taxonomia.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="taxonomia.json não encontrado")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


class TaxonomyAddRequest(BaseModel):
    valor: str


def _add_taxonomy_value(field_name: str, body: TaxonomyAddRequest) -> dict:
    path = CONFIG_ROOT / "taxonomia.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="taxonomia.json não encontrado")
    data = json.loads(path.read_text(encoding="utf-8"))
    valor = body.valor.strip()
    values = data.get(field_name)
    if not isinstance(values, list):
        raise HTTPException(status_code=400, detail=f"Campo inválido na taxonomia: {field_name}")
    if valor and valor not in values:
        values.append(valor)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {field_name: values}


@router.post("/taxonomy/categoria")
def add_categoria(body: TaxonomyAddRequest):
    return _add_taxonomy_value("categorias", body)


@router.post("/taxonomy/natureza")
def add_natureza(body: TaxonomyAddRequest):
    return _add_taxonomy_value("natureza", body)


@router.post("/taxonomy/recorrencia")
def add_recorrencia(body: TaxonomyAddRequest):
    return _add_taxonomy_value("recorrencia", body)


@router.post("/taxonomy/contexto")
def add_contexto(body: TaxonomyAddRequest):
    return _add_taxonomy_value("contextos", body)
