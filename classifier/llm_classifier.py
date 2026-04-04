from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from models.transaction import Classificacao, Transaction

from classifier.llm_client import LLMClient

logger = logging.getLogger(__name__)

_BATCH_SIZE = 20
_MAX_ATTEMPTS = 2

_JSON_ARRAY_RE = re.compile(r"\[[\s\S]*\]")


def _compact_json(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def _build_system_prompt(taxonomia: dict, perfil: dict) -> str:
    perfil_ctx = {
        "contexto_padrao": perfil.get("contexto_padrao"),
        "viagens": perfil.get("viagens"),
        "notas": perfil.get("notas_classificacao"),
    }
    return (
        "Você é um classificador de transações financeiras pessoais brasileiras.\n"
        "Responda APENAS com um array JSON válido. Sem texto, sem markdown, sem explicações.\n\n"
        "Taxonomia disponível:\n"
        f"{_compact_json(taxonomia)}\n\n"
        "Perfil do usuário (contexto para inferência):\n"
        f"{_compact_json(perfil_ctx)}\n"
    )


def _build_user_prompt(batch: list[Transaction]) -> str:
    items = []
    for transaction in batch:
        items.append(
            {
                "id": transaction.id,
                "data": transaction.data.isoformat(),
                "descricao_original": transaction.descricao_original,
                "valor": transaction.valor,
                "tipo": transaction.tipo,
                "meio": transaction.meio,
            }
        )
    instruction = (
        "Classifique cada transação abaixo. Para cada item retorne um objeto com:\n"
        "id, categoria, natureza, recorrencia, compromisso, contexto, confianca (número 0.0 a 1.0).\n"
        "Se confianca < 0.75, inclua motivo_duvida (string, no máximo 10 palavras).\n"
        "Use null quando não souber. compromisso deve ser um de: a_vista, parcela, assinatura ou null.\n\n"
    )
    return instruction + _compact_json(items)


def _extract_json_array(raw: str) -> str | None:
    stripped = raw.strip()
    if stripped.startswith("["):
        return stripped
    match = _JSON_ARRAY_RE.search(stripped)
    return match.group(0) if match else None


def _parse_llm_payload(raw: str) -> list[dict]:
    extracted = _extract_json_array(raw)
    if not extracted:
        raise ValueError("JSON array não encontrado na resposta")
    parsed = json.loads(extracted)
    if not isinstance(parsed, list):
        raise ValueError("Resposta não é um array JSON")
    return [item for item in parsed if isinstance(item, dict)]


def _apply_llm_item(transaction: Transaction, item: dict) -> None:
    prior = transaction.classificacao

    def pick_str(key: str) -> str | None:
        value = item.get(key)
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def coalesce(new: str | None, fallback: str | None) -> str | None:
        return new if new is not None else fallback

    confianca_raw = item.get("confianca", 0.0)
    try:
        confianca = float(confianca_raw)
    except (TypeError, ValueError):
        confianca = 0.0
    confianca = max(0.0, min(1.0, confianca))

    compromisso = pick_str("compromisso")
    if compromisso and compromisso not in ("a_vista", "parcela", "assinatura"):
        compromisso = None
    compromisso = coalesce(compromisso, prior.compromisso)

    motivo = pick_str("motivo_duvida")
    words = motivo.split() if motivo else []
    if len(words) > 10:
        motivo = " ".join(words[:10])

    transaction.classificacao = Classificacao(
        categoria=coalesce(pick_str("categoria"), prior.categoria),
        natureza=coalesce(pick_str("natureza"), prior.natureza),
        recorrencia=coalesce(pick_str("recorrencia"), prior.recorrencia),
        compromisso=compromisso,  # type: ignore[arg-type]
        contexto=coalesce(pick_str("contexto"), prior.contexto),
        metodo="llm",
        confianca=confianca,
        motivo_duvida=motivo,
    )


def classify_with_llm(
    pending: list[Transaction],
    *,
    taxonomia_path: Path,
    perfil_path: Path,
    client: LLMClient | None = None,
) -> tuple[int, int]:
    """
    Classifica transações pendentes em lotes. Retorna (sucesso, falhas de lote).
    """
    if not pending:
        return 0, 0

    taxonomia: dict = {}
    if taxonomia_path.exists():
        with taxonomia_path.open(encoding="utf-8") as handle:
            taxonomia = json.load(handle)
    perfil: dict = {}
    if perfil_path.exists():
        with perfil_path.open(encoding="utf-8") as handle:
            perfil = json.load(handle)

    system_prompt = _build_system_prompt(taxonomia, perfil)
    llm = client or LLMClient()

    success_count = 0
    batch_failures = 0
    by_id = {transaction.id: transaction for transaction in pending}

    for start in range(0, len(pending), _BATCH_SIZE):
        batch = pending[start : start + _BATCH_SIZE]
        user_prompt = _build_user_prompt(batch)
        raw_response = ""
        parsed: list[dict] = []
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                raw_response = llm.complete(system_prompt, user_prompt)
                parsed = _parse_llm_payload(raw_response)
                break
            except Exception:
                logger.warning(
                    "Tentativa %s/%s de parse LLM falhou para lote iniciando em %s",
                    attempt,
                    _MAX_ATTEMPTS,
                    start,
                    exc_info=True,
                )
        else:
            logger.warning(
                "Lote inteiro mantido pendente após %s tentativas (índices %s–%s)",
                _MAX_ATTEMPTS,
                start,
                start + len(batch) - 1,
            )
            batch_failures += 1
            continue

        seen_ids = set()
        for item in parsed:
            transaction_id = str(item.get("id", ""))
            transaction = by_id.get(transaction_id)
            if not transaction:
                continue
            seen_ids.add(transaction_id)
            _apply_llm_item(transaction, item)
            success_count += 1

        for transaction in batch:
            if transaction.id not in seen_ids:
                logger.warning(
                    "Transação %s não retornada pelo LLM; mantida pendente",
                    transaction.id,
                )

    return success_count, batch_failures
