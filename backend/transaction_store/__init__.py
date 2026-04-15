from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import TypeAdapter

from backend.models.transaction import Classificacao, Transaction, dedupe_transactions

logger = logging.getLogger(__name__)

_transaction_list_adapter = TypeAdapter(list[Transaction])


def classificacao_filename_for_month(month_key: str) -> str:
    return f"classificacao_{month_key}.json"


def load_overlay_by_id(month_dir: Path, month_key: str) -> dict[str, dict]:
    path = month_dir / classificacao_filename_for_month(month_key)
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    return dict(payload.get("by_id", {}))


def merge_classificacao(base: Classificacao, patch: dict) -> Classificacao:
    data = base.model_dump()
    for key, value in patch.items():
        if key not in data:
            continue
        if value is not None:
            data[key] = value
    return Classificacao(**data)


def apply_overlay(transaction: Transaction, overlay: dict[str, dict]) -> Transaction:
    patch = overlay.get(transaction.id)
    if not patch:
        return transaction
    transaction.classificacao = merge_classificacao(transaction.classificacao, patch)
    return transaction


def load_transactions_json(path: Path) -> list[Transaction]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        raw = json.load(handle)
    return _transaction_list_adapter.validate_python(raw)


def load_month_transactions(processed_root: Path, month_key: str) -> list[Transaction]:
    month_dir = processed_root / month_key
    overlay = load_overlay_by_id(month_dir, month_key)
    combined: list[Transaction] = []
    for filename in ("fatura.json", "extrato.json"):
        for transaction in load_transactions_json(month_dir / filename):
            combined.append(apply_overlay(transaction, overlay))
    return dedupe_transactions(combined)


def save_classificacao_snapshot(month_dir: Path, month_key: str, transactions: list[Transaction]) -> Path:
    month_dir.mkdir(parents=True, exist_ok=True)
    path = month_dir / classificacao_filename_for_month(month_key)
    by_id = {transaction.id: transaction.classificacao.model_dump(mode="json") for transaction in transactions}
    payload = {"version": 1, "month": month_key, "by_id": by_id}
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    logger.info("Classificação salva em %s", path)
    return path
