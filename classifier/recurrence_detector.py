from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime
from pathlib import Path
from statistics import mean, pstdev

import duckdb

from models.transaction import Transaction

logger = logging.getLogger(__name__)

_RE_PIX_PF = re.compile(r"PIX\s+", re.IGNORECASE)


def _month_key_to_date(month_key: str) -> date | None:
    try:
        year_s, month_s = month_key.split("-", 1)
        return date(int(year_s), int(month_s), 1)
    except (ValueError, IndexError):
        return None


def _collect_json_paths(processed_root: Path, anchor: date, window_days: int) -> list[str]:
    paths: list[str] = []
    start_limit = date.fromordinal(anchor.toordinal() - window_days)
    for month_dir in sorted(processed_root.iterdir()):
        if not month_dir.is_dir():
            continue
        month_anchor = _month_key_to_date(month_dir.name)
        if month_anchor is None:
            continue
        if month_anchor > anchor or month_anchor < date(start_limit.year, start_limit.month, 1):
            continue
        for name in ("fatura.json", "extrato.json"):
            candidate = month_dir / name
            if candidate.exists():
                paths.append(str(candidate.resolve()))
    return paths


def _looks_like_pix_pessoa(descricao: str) -> bool:
    upper = descricao.upper()
    if "PIX" not in upper:
        return False
    if any(token in upper for token in ("BOLETO", "TAX", "DARF", "GOVERNO", "PREFEITURA")):
        return False
    return bool(_RE_PIX_PF.search(descricao))


def _needs_pix_followup(transaction: Transaction) -> bool:
    if not _looks_like_pix_pessoa(transaction.descricao_original):
        return False
    if transaction.classificacao.categoria:
        return False
    if transaction.classificacao.metodo == "regra":
        return False
    return True


def run_recurrence_detection(
    processed_root: Path,
    month_key: str,
    transactions: list[Transaction],
) -> Path | None:
    """
    DuckDB sobre JSONs em janela de 60 dias; gera `suggestions.json` quando aplicável.
    """
    month_dir = processed_root / month_key
    anchor = _month_key_to_date(month_key)
    if anchor is None:
        logger.warning("Mês inválido para recorrência: %s", month_key)
        return None

    json_paths = _collect_json_paths(processed_root, anchor, 60)
    grouped: dict[str, tuple[int, list[float]]] = {}

    if json_paths:
        con = duckdb.connect(database=":memory:")
        try:
            rows = con.execute(
                """
                WITH raw AS (
                    SELECT * FROM read_json_auto(?)
                )
                SELECT
                    descricao_original,
                    COUNT(*) AS occurrences,
                    LIST(valor ORDER BY try_strptime(CAST(data AS VARCHAR), '%Y-%m-%d')) AS valores
                FROM raw
                WHERE try_strptime(CAST(data AS VARCHAR), '%Y-%m-%d') IS NOT NULL
                  AND try_strptime(CAST(data AS VARCHAR), '%Y-%m-%d')
                      >= CAST(? AS DATE) - INTERVAL 60 DAY
                GROUP BY 1
                HAVING COUNT(*) >= 2
                """,
                [json_paths, anchor.isoformat()],
            ).fetchall()
            for descricao_original, occurrences, valores in rows:
                if descricao_original is None:
                    continue
                valores_list = [float(value) for value in (valores or []) if value is not None]
                grouped[str(descricao_original)] = (int(occurrences), valores_list)
        except Exception:
            logger.warning("DuckDB recorrência falhou; sugestões limitadas", exc_info=True)
        finally:
            con.close()

    suggestions: list[dict] = []
    seen_ids: set[str] = set()

    for transaction in transactions:
        desc = transaction.descricao_original
        bucket = grouped.get(desc)
        if not bucket:
            continue
        occurrences, valores_list = bucket
        if len(valores_list) < 2:
            continue
        avg_val = mean(valores_list)
        deviation = (pstdev(valores_list) / avg_val) if avg_val else 1.0
        rec_sug = "Fixa" if deviation < 0.10 else "Variável recorrente"
        item: dict = {
            "transaction_id": transaction.id,
            "descricao_original": desc,
            "tipo": "recorrencia_valor",
            "recorrencia_sugerida": rec_sug,
            "ocorrencias": occurrences,
            "desvio_relativo": round(deviation, 4),
        }
        if _needs_pix_followup(transaction):
            item["tipo"] = "pix_pessoa_recorrente"
            item["nota"] = "Pix para pessoa física sem categoria; confirmar via review"
        suggestions.append(item)
        seen_ids.add(transaction.id)

    for transaction in transactions:
        if transaction.id in seen_ids:
            continue
        if not _needs_pix_followup(transaction):
            continue
        if transaction.descricao_original not in grouped:
            continue
        suggestions.append(
            {
                "transaction_id": transaction.id,
                "descricao_original": transaction.descricao_original,
                "tipo": "pix_pessoa_recorrente_candidato",
                "recorrencia_sugerida": "Variável recorrente",
                "nota": "Recorrente na janela; confirmar categoria via review",
            }
        )

    if not suggestions:
        return None

    month_dir.mkdir(parents=True, exist_ok=True)
    output_path = month_dir / "suggestions.json"
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "month": month_key,
        "items": suggestions,
    }
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    logger.info("Sugestões de recorrência: %s (%s itens)", output_path, len(suggestions))
    return output_path
