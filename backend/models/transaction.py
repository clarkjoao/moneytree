from __future__ import annotations

from datetime import date
from typing import Any, Literal
from uuid import uuid4

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


class Classificacao(BaseModel):
    categoria: str | None = None
    natureza: str | None = None
    recorrencia: str | None = None
    compromisso: CompromissoTipo | None = None
    contexto: str | None = None
    metodo: MetodoClassificacao = "pendente"
    confianca: float = Field(default=0.0, ge=0.0, le=1.0)
    motivo_duvida: str | None = None


class Transaction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    data: date
    descricao_original: str
    valor: float = Field(gt=0, description="Sempre positivo; usar tipo para direção")
    tipo: Literal["debito", "credito"]
    meio: Literal["cartao_credito", "debito_pix"]
    fonte: str
    cartao_final: str | None = None
    parcela_info: ParcelaInfo | None = None
    classificacao: Classificacao = Field(default_factory=Classificacao)
    metadados: dict[str, Any] | None = None
