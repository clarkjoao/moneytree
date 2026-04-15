from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ParcelaInfo(BaseModel):
    numero: int = Field(ge=1)
    total: int = Field(ge=1)

    @model_validator(mode="after")
    def total_gte_numero(self) -> ParcelaInfo:
        if self.total < self.numero:
            raise ValueError("total must be >= numero")
        return self


CompromissoTipo = Literal["a_vista", "parcela", "assinatura"]


MetodoClassificacao = Literal["regra", "pendente", "llm", "confirmado"]

_RE_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_RE_PARCELA_TOKEN = re.compile(r"\b\d{1,2}/\d{1,2}\b")


def _normalize_text_key(value: str) -> str:
    normalized = (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    compact = _RE_NON_ALNUM.sub(" ", normalized).strip()
    return re.sub(r"\s+", " ", compact)


def _amount_cents(value: float) -> str:
    return str(int(round(value * 100)))


def _build_hash(prefix: str, parts: list[str]) -> str:
    payload = "|".join(parts)
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"


def _descricao_sem_parcela(descricao: str) -> str:
    sem_parcela = _RE_PARCELA_TOKEN.sub(" ", descricao)
    return _normalize_text_key(sem_parcela)


class Classificacao(BaseModel):
    categoria: str | None = None
    natureza: str | None = None
    recorrencia: str | None = None
    compromisso: CompromissoTipo | None = None
    contexto: str | None = None
    labels: list[str] = Field(default_factory=list)
    metodo: MetodoClassificacao = "pendente"
    confianca: float = Field(default=0.0, ge=0.0, le=1.0)
    motivo_duvida: str | None = None


class Transaction(BaseModel):
    id: str | None = None
    data: date
    descricao_original: str
    valor: float = Field(gt=0, description="Sempre positivo; usar tipo para direção")
    tipo: Literal["debito", "credito"]
    meio: Literal["cartao_credito", "debito_pix"]
    fonte: str
    cartao_final: str | None = None
    parcela_info: ParcelaInfo | None = None
    compra_id: str | None = None
    classificacao: Classificacao = Field(default_factory=Classificacao)
    metadados: dict[str, Any] | None = None

    @model_validator(mode="after")
    def ensure_stable_identity(self) -> Transaction:
        if not self.id:
            self.id = _build_hash(
                "tx",
                [
                    self.data.isoformat(),
                    _normalize_text_key(self.descricao_original),
                    _amount_cents(self.valor),
                    self.tipo,
                    self.meio,
                    self.cartao_final or "",
                    str(self.parcela_info.numero if self.parcela_info else ""),
                    str(self.parcela_info.total if self.parcela_info else ""),
                ],
            )
        if self.parcela_info and not self.compra_id:
            self.compra_id = _build_hash(
                "cmp",
                [
                    self.data.isoformat(),
                    _descricao_sem_parcela(self.descricao_original),
                    _amount_cents(self.valor),
                    self.tipo,
                    self.meio,
                    self.cartao_final or "",
                    str(self.parcela_info.total),
                ],
            )
        return self


def dedupe_transactions(transactions: list[Transaction]) -> list[Transaction]:
    unique: dict[str, Transaction] = {}
    for transaction in transactions:
        unique.setdefault(transaction.id or "", transaction)
    return list(unique.values())
