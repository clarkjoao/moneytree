from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

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
    progress_callback: Callable[[dict[str, int | str]], None] | None = None,
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
            "pendentes_antes_llm": 0,
            "pendentes_finais": 0,
            "classificadas": 0,
        }

    if progress_callback is not None:
        progress_callback(
            {
                "phase": "loaded",
                "total": len(transactions),
                "pending": sum(1 for transaction in transactions if transaction.classificacao.metodo == "pendente"),
                "classified": sum(1 for transaction in transactions if transaction.classificacao.metodo != "pendente"),
            }
        )

    rule_hits = apply_rule_engine(transactions, regras, perfil)
    context_touch = apply_context_engine(transactions, perfil)
    pending_after_rules = [
        transaction for transaction in transactions if transaction.classificacao.metodo == "pendente"
    ]
    if progress_callback is not None:
        progress_callback(
            {
                "phase": "rules_applied",
                "total": len(transactions),
                "pending": len(pending_after_rules),
                "classified": len(transactions) - len(pending_after_rules),
                "por_regra": rule_hits,
                "contexto_touch": context_touch,
            }
        )

    pending = pending_after_rules
    llm_ok = 0
    llm_batches_failed = 0
    if use_llm and pending:
        try:
            llm_ok, llm_batches_failed = classify_with_llm(
                pending,
                taxonomia_path=taxonomia_path,
                perfil_path=config_dir / "perfil.json",
                client=llm_client,
                progress_callback=lambda payload: progress_callback(
                    {
                        "phase": "llm_running",
                        "total": len(transactions),
                        "pending": max(len(pending) - int(payload["success"]), 0),
                        "classified": (len(transactions) - len(pending)) + int(payload["success"]),
                        "llm_processed": int(payload["processed"]),
                        "llm_total": int(payload["total"]),
                        "lotes_llm_falhos": int(payload["batch_failures"]),
                    }
                )
                if progress_callback is not None
                else None,
            )
        except Exception:
            logger.warning("LLM indisponível ou erro de configuração; etapa ignorada", exc_info=True)

    run_recurrence_detection(processed_root, month_key, transactions)
    save_classificacao_snapshot(month_dir, month_key, transactions)
    review_path = write_review_csv(month_dir, transactions)
    revisao_count = sum(1 for transaction in transactions if needs_human_review(transaction))
    pending_final = sum(1 for transaction in transactions if transaction.classificacao.metodo == "pendente")
    classified_total = len(transactions) - pending_final

    if progress_callback is not None:
        progress_callback(
            {
                "phase": "finished",
                "total": len(transactions),
                "pending": pending_final,
                "classified": classified_total,
                "review": revisao_count,
                "por_llm": llm_ok,
                "lotes_llm_falhos": llm_batches_failed,
            }
        )

    logger.info("Classificação concluída; revisão em %s", review_path)

    return {
        "total": len(transactions),
        "por_regra": rule_hits,
        "contexto_touch": context_touch,
        "por_llm": llm_ok,
        "lotes_llm_falhos": llm_batches_failed,
        "revisao": revisao_count,
        "pendentes_antes_llm": len(pending),
        "pendentes_finais": pending_final,
        "classificadas": classified_total,
    }
