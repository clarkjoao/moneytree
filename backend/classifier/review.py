from __future__ import annotations

import csv
import logging
import os
import subprocess
import sys
from pathlib import Path

from backend.models.transaction import Classificacao, Transaction

from backend.classifier.rule_engine import append_exact_rule
from backend.transaction_store import load_month_transactions, save_classificacao_snapshot

logger = logging.getLogger(__name__)

_REVIEW_COLUMNS = [
    "id",
    "data",
    "descricao_original",
    "valor",
    "sugestao_categoria",
    "sugestao_natureza",
    "sugestao_contexto",
    "confianca",
    "motivo_duvida",
    "confirmado",
]


def needs_human_review(transaction: Transaction) -> bool:
    classification = transaction.classificacao
    if classification.metodo == "pendente":
        return True
    return classification.confianca < 0.75


def build_review_rows(transactions: list[Transaction]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for transaction in transactions:
        if not needs_human_review(transaction):
            continue
        classification = transaction.classificacao
        rows.append(
            {
                "id": transaction.id,
                "data": transaction.data.isoformat(),
                "descricao_original": transaction.descricao_original,
                "valor": str(transaction.valor),
                "sugestao_categoria": classification.categoria or "",
                "sugestao_natureza": classification.natureza or "",
                "sugestao_contexto": classification.contexto or "",
                "confianca": str(classification.confianca),
                "motivo_duvida": classification.motivo_duvida or "",
                "confirmado": "",
            }
        )
    return rows


def write_review_csv(month_dir: Path, transactions: list[Transaction]) -> Path:
    month_dir.mkdir(parents=True, exist_ok=True)
    path = month_dir / "review.csv"
    rows = build_review_rows(transactions)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_REVIEW_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    logger.info("CSV de revisão: %s (%s linhas)", path, len(rows))
    return path


def open_csv_for_editing(csv_path: Path) -> None:
    editor = os.environ.get("EDITOR", "").strip()
    if editor:
        subprocess.run([editor, str(csv_path)], check=False)
        return
    if sys.platform == "darwin":
        subprocess.run(["open", "-t", str(csv_path)], check=False)
        return
    if sys.platform.startswith("win"):
        os.startfile(str(csv_path))  # type: ignore[attr-defined]
        return
    logger.info("Defina EDITOR ou abra manualmente: %s", csv_path)


def _is_confirmed(value: str) -> bool:
    normalized = (value or "").strip().lower()
    return normalized in ("1", "sim", "s", "true", "yes", "x", "ok", "y")


def _empty_to_none(value: str | None) -> str | None:
    text = (value or "").strip()
    return text or None


def apply_review_csv(
    month_dir: Path,
    month_key: str,
    csv_path: Path,
    regras_path: Path,
    processed_root: Path,
) -> int:
    if not csv_path.exists():
        logger.error("CSV não encontrado: %s", csv_path)
        return 0

    transactions = load_month_transactions(processed_root, month_key)
    by_id = {transaction.id: transaction for transaction in transactions}

    applied = 0
    with csv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if not _is_confirmed(row.get("confirmado", "")):
                continue
            transaction_id = (row.get("id") or "").strip()
            transaction = by_id.get(transaction_id)
            if not transaction:
                logger.warning("ID desconhecido no CSV de revisão: %s", transaction_id)
                continue

            prior = transaction.classificacao
            transaction.classificacao = Classificacao(
                categoria=_empty_to_none(row.get("sugestao_categoria")) or prior.categoria,
                natureza=_empty_to_none(row.get("sugestao_natureza")) or prior.natureza,
                recorrencia=prior.recorrencia,
                compromisso=prior.compromisso,
                contexto=_empty_to_none(row.get("sugestao_contexto")) or prior.contexto,
                metodo="confirmado",
                confianca=1.0,
                motivo_duvida=None,
            )
            append_exact_rule(regras_path, transaction.descricao_original, transaction.classificacao)
            applied += 1

    save_classificacao_snapshot(month_dir, month_key, transactions)
    logger.info("Revisão aplicada: %s transações atualizadas", applied)
    return applied
