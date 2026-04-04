from __future__ import annotations

import json
import logging
from pathlib import Path

from models.transaction import Classificacao, Transaction

logger = logging.getLogger(__name__)

_CLASSIFICATION_FIELDS = set(Classificacao.model_fields.keys()) - {"metodo", "confianca", "motivo_duvida"}


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _rule_payload_to_updates(rule: dict) -> dict:
    return {key: rule[key] for key in _CLASSIFICATION_FIELDS if key in rule}


def _apply_updates(transaction: Transaction, updates: dict) -> None:
    prior = transaction.classificacao.model_dump()
    merged = {**prior, **updates, "metodo": "regra", "confianca": 1.0, "motivo_duvida": None}
    transaction.classificacao = Classificacao(**merged)


def _match_por_descricao(descricao: str, por_descricao: dict) -> dict | None:
    if not por_descricao:
        return None
    direct = por_descricao.get(descricao)
    if isinstance(direct, dict):
        return direct

    substring_entries: list[tuple[int, dict]] = []
    for key, value in por_descricao.items():
        key_str = str(key)
        if not key_str.startswith("~"):
            continue
        if not isinstance(value, dict):
            continue
        needle = key_str[1:]
        if needle and needle.upper() in descricao.upper():
            substring_entries.append((len(needle), value))
    if substring_entries:
        substring_entries.sort(key=lambda item: item[0], reverse=True)
        return substring_entries[0][1]
    return None


def _legacy_padroes(descricao_upper: str, padroes: list) -> dict | None:
    for padrao in padroes:
        needle = str(padrao.get("contem", "")).upper()
        if needle and needle in descricao_upper:
            return padrao
    return None


def _legacy_mapeamentos(descricao_upper: str, mapeamentos: list) -> dict | None:
    for mapping in mapeamentos:
        needle = str(mapping.get("contem", "")).upper()
        if needle and needle in descricao_upper:
            return mapping
    return None


def apply_rule_engine(
    transactions: list[Transaction],
    regras: dict,
    perfil: dict,
) -> int:
    """
    Aplica regras determinísticas. Retorna quantidade de transações atualizadas.
    """
    por_descricao = regras.get("por_descricao") or {}
    if not isinstance(por_descricao, dict):
        por_descricao = {}
    padroes = regras.get("padroes_descricao") or []
    mapeamentos = regras.get("mapeamentos") or []

    contas = perfil.get("contas_proprias") or []
    pessoas = perfil.get("pessoas_conhecidas") or {}

    updated = 0
    for transaction in transactions:
        if transaction.classificacao.metodo != "pendente":
            continue

        descricao = transaction.descricao_original
        desc_upper = descricao.upper()

        matched = False
        for conta in contas:
            conta_str = str(conta).strip()
            if conta_str and conta_str.upper() in desc_upper:
                _apply_updates(
                    transaction,
                    {
                        "categoria": "Transferência Interna",
                        "natureza": "Transferência",
                        "recorrencia": "Pontual",
                        "compromisso": None,
                        "contexto": None,
                    },
                )
                matched = True
                updated += 1
                break
        if matched:
            continue

        for nome, attrs in pessoas.items():
            if str(nome).upper() in desc_upper:
                if isinstance(attrs, dict):
                    _apply_updates(transaction, _rule_payload_to_updates(attrs))
                matched = True
                updated += 1
                break
        if matched:
            continue

        rule_hit = _match_por_descricao(descricao, por_descricao)
        if rule_hit:
            _apply_updates(transaction, _rule_payload_to_updates(rule_hit))
            updated += 1
            continue

        legacy = _legacy_padroes(desc_upper, padroes)
        if legacy:
            _apply_updates(transaction, _rule_payload_to_updates(legacy))
            updated += 1
            continue

        legacy_map = _legacy_mapeamentos(desc_upper, mapeamentos)
        if legacy_map:
            _apply_updates(transaction, _rule_payload_to_updates(legacy_map))
            updated += 1

    return updated


def append_exact_rule(regras_path: Path, descricao_original: str, classification: Classificacao) -> None:
    """Aprende regra com chave exata igual a descricao_original."""
    if regras_path.exists():
        data = load_json(regras_path)
    else:
        data = {"por_descricao": {}, "padroes_descricao": [], "mapeamentos": []}
    por = data.setdefault("por_descricao", {})
    if not isinstance(por, dict):
        data["por_descricao"] = {}
        por = data["por_descricao"]
    updates = _rule_payload_to_updates(classification.model_dump())
    por[descricao_original] = updates
    regras_path.parent.mkdir(parents=True, exist_ok=True)
    with regras_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    logger.info("Regra aprendida (exata): %s", descricao_original[:60])
