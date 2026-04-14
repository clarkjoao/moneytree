import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()
ROOT = Path(__file__).resolve().parents[2]
PERFIL_PATH = ROOT / "config" / "perfil.json"


@router.get("/perfil")
def get_perfil():
    if not PERFIL_PATH.exists():
        raise HTTPException(status_code=404, detail="perfil.json não encontrado")
    with PERFIL_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


class EstabelecimentoAncora(BaseModel):
    padrao: str
    contexto: str


class PessoaConhecida(BaseModel):
    categoria: str | None = None
    natureza: str | None = None
    recorrencia: str | None = None


class Viagem(BaseModel):
    destino: str
    motivo: str
    frequencia: str


class PerfilPayload(BaseModel):
    contexto_padrao: str | None = None
    cidades_contexto: dict[str, str] | None = None
    estabelecimentos_ancora: list[EstabelecimentoAncora] | None = None
    contas_proprias: list[str] | None = None
    pessoas_conhecidas: dict[str, PessoaConhecida] | None = None
    viagens: list[Viagem] | None = None


@router.put("/perfil")
def update_perfil(payload: PerfilPayload):
    if not PERFIL_PATH.exists():
        raise HTTPException(status_code=404, detail="perfil.json não encontrado")
    with PERFIL_PATH.open("r", encoding="utf-8") as f:
        current = json.load(f)

    updates: dict[str, Any] = {k: v for k, v in payload.model_dump().items() if v is not None}

    # Serialize nested Pydantic models to plain dicts
    if "pessoas_conhecidas" in updates:
        updates["pessoas_conhecidas"] = {
            name: (pc if isinstance(pc, dict) else pc)
            for name, pc in updates["pessoas_conhecidas"].items()
        }

    current.update(updates)

    with PERFIL_PATH.open("w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)

    return current
