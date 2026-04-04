from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any

from models.transaction import Transaction

logger = logging.getLogger(__name__)

_RE_CIDADE_SUFIXO = re.compile(r"\.([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ]+(?: [A-ZÁÀÂÃÉÊÍÓÔÕÚÇ]+)*)\s*$")


def _parse_viagem_window(entry: dict[str, Any]) -> tuple[date | None, date | None]:
    inicio_str = entry.get("inicio")
    fim_str = entry.get("fim")
    if not inicio_str or not fim_str:
        return None, None
    try:
        inicio = date.fromisoformat(str(inicio_str))
        fim = date.fromisoformat(str(fim_str))
        return inicio, fim
    except ValueError:
        return None, None


def _viagem_context_for_date(target: date, viagens: list) -> str | None:
    for entry in viagens:
        if not isinstance(entry, dict):
            continue
        inicio, fim = _parse_viagem_window(entry)
        if inicio and fim and inicio <= target <= fim:
            return str(entry.get("contexto_viagem") or entry.get("destino") or "Viagem")
        motivo = entry.get("motivo")
        destino = entry.get("destino")
        if motivo and "trabalho" in str(motivo).lower() and destino:
            if "paulo" in str(destino).lower() and target.weekday() < 5:
                return "Trabalho SP"
    return None


def _normalize_city_token(token: str) -> str:
    return (
        token.upper()
        .replace("Á", "A")
        .replace("Ã", "A")
        .replace("Â", "A")
        .replace("É", "E")
        .replace("Í", "I")
        .replace("Ó", "O")
        .replace("Õ", "O")
        .replace("Ú", "U")
        .replace("Ç", "C")
    )


def apply_context_engine(transactions: list[Transaction], perfil: dict) -> int:
    """
    Preenche `contexto` por hierarquia (cidade no nome > âncora > janela de viagem > padrão).
    """
    cidades_map = perfil.get("cidades_contexto") or {}
    if not isinstance(cidades_map, dict):
        cidades_map = {}
    normalized_cidades: dict[str, str] = {}
    for city_key, contexto in cidades_map.items():
        normalized_cidades[_normalize_city_token(str(city_key))] = str(contexto)

    ancora_list = perfil.get("estabelecimentos_ancora") or []
    if not isinstance(ancora_list, list):
        ancora_list = []

    viagens = perfil.get("viagens") or []
    default_contexto = str(perfil.get("contexto_padrao") or "Outros")

    touched = 0
    for transaction in transactions:
        desc_upper = transaction.descricao_original.upper()

        contexto_val: str | None = None

        city_match = _RE_CIDADE_SUFIXO.search(desc_upper.strip())
        if city_match:
            token = _normalize_city_token(city_match.group(1))
            mapped = normalized_cidades.get(token)
            if mapped:
                contexto_val = mapped

        if contexto_val is None:
            for anchor in ancora_list:
                if not isinstance(anchor, dict):
                    continue
                padrao = str(anchor.get("padrao", "")).upper()
                if padrao and padrao in desc_upper:
                    contexto_val = str(anchor.get("contexto") or "Viagem")
                    break

        if contexto_val is None:
            contexto_val = _viagem_context_for_date(transaction.data, viagens)

        if contexto_val is None:
            contexto_val = default_contexto

        if transaction.classificacao.contexto != contexto_val:
            transaction.classificacao.contexto = contexto_val
            touched += 1

    return touched
