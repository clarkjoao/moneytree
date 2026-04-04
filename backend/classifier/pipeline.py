from __future__ import annotations

import logging
from pathlib import Path

from backend.models.transaction import Transaction

from backend.classifier.context_engine import apply_context_engine
from backend.classifier.llm_classifier import classify_with_llm
from backend.classifier.llm_client import LLMClient
from backend.classifier.recurrence_detector import run_recurrence_detection
from backend.classifier.review import needs_human_review, write_review_csv
from backend.classifier.rule_engine import apply_rule_engine, load_json
from backend.transaction_store import load_month_transactions, save_classificacao_snapshot

logger = logging.getLogger(__name__)


def run_classify_month(
    project_root: Path,
    month_key: str,
    config_dir: Path,
    *,
    use_llm: bool = True,
    llm_client: LLMClient | None = None,
) -> dict[str, int]:
    processed_root = project_root / "data" / "processed"
    month_dir = processed_root / month_key

    regras = load_json(config_dir / "regras.json")
    perfil = load_json(config_dir / "perfil.json")
    taxonomia_path = config_dir / "taxonomia.json"

    transactions = load_month_transactions(processed_root, month_key)
    if not transactions:
        logger.warning("Nenhuma transação em %s", month_dir)
        return {
            "total": 0,
            "por_regra": 0,
            "contexto_touch": 0,
            "por_llm": 0,
            "lotes_llm_falhos": 0,
            "revisao": 0,
        }

    rule_hits = apply_rule_engine(transactions, regras, perfil)
    context_touch = apply_context_engine(transactions, perfil)

    pending = [transaction for transaction in transactions if transaction.classificacao.metodo == "pendente"]
    llm_ok = 0
    llm_batches_failed = 0
    if use_llm and pending:
        try:
            llm_ok, llm_batches_failed = classify_with_llm(
                pending,
                taxonomia_path=taxonomia_path,
                perfil_path=config_dir / "perfil.json",
                client=llm_client,
            )
        except Exception:
            logger.warning("LLM indisponível ou erro de configuração; etapa ignorada", exc_info=True)

    run_recurrence_detection(processed_root, month_key, transactions)
    save_classificacao_snapshot(month_dir, month_key, transactions)
    review_path = write_review_csv(month_dir, transactions)
    revisao_count = sum(1 for transaction in transactions if needs_human_review(transaction))

    logger.info("Classificação concluída; revisão em %s", review_path)

    return {
        "total": len(transactions),
        "por_regra": rule_hits,
        "contexto_touch": context_touch,
        "por_llm": llm_ok,
        "lotes_llm_falhos": llm_batches_failed,
        "revisao": revisao_count,
    }

