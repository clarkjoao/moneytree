from __future__ import annotations

import json
import logging
import re
from calendar import monthrange
from datetime import date
from pathlib import Path
from typing import Any

import pdfplumber

from backend.models.transaction import Classificacao, Transaction
from backend.parsers.base_parser import BaseParser
from backend.parsers.banks.itau._utils import _group_words_by_line

logger = logging.getLogger(__name__)

_SALDO_X_MIN = 490.0

_RE_EXTRATO_LINE = re.compile(
    r"^(\d{2}/\d{2}/\d{4})\s+(.+?)\s+"
    r"(-?\d{1,3}(?:\.\d{3})*,\d{2}|-?\d+,\d{2})\s*(?:-?\d[\d.,]*)?\s*$",
)
_RE_DATE_FULL = re.compile(r"^\d{2}/\d{2}/\d{4}$")
_RE_AMOUNT = re.compile(r"^-?\d{1,3}(?:\.\d{3})*,\d{2}$")


def _parse_br_float(amount_token: str) -> float:
    normalized = amount_token.replace(".", "").replace(",", ".")
    return float(normalized)


def _parse_extrato_date(token: str, default_year: int) -> date | None:
    parts = token.split("/")
    if len(parts) == 2:
        day, month = int(parts[0]), int(parts[1])
        year = default_year
    elif len(parts) == 3:
        day, month, year_part = int(parts[0]), int(parts[1]), int(parts[2])
        year = 2000 + year_part if year_part < 100 else year_part
    else:
        return None
    last = monthrange(year, month)[1]
    if day > last:
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def extrato_metadata_kind(description_upper: str) -> str | None:
    if description_upper.startswith("ITAU BLACK"):
        return "pagamento_fatura"
    if "FATURA PAGA PERSON MULTI" in description_upper:
        return "pagamento_fatura"
    if description_upper.startswith("SALDO DO DIA"):
        return "saldo"
    if "REND PAGO APLIC AUT MAIS" in description_upper:
        return "rendimento_aplicacao"
    if description_upper.startswith("COR RENDIMENTO"):
        return "rendimento_aplicacao"
    return None


def _append_extrato_metadados(month_dir: Path, record: dict[str, Any]) -> None:
    month_dir.mkdir(parents=True, exist_ok=True)
    path = month_dir / "extrato_metadados.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _handle_metadata_line(
    description: str,
    amount_token: str,
    *,
    fonte: str,
    month_dir: Path | None,
) -> str | None:
    metadata_kind = extrato_metadata_kind(description.upper())
    if not metadata_kind:
        return None

    if month_dir is not None and metadata_kind in {"rendimento_aplicacao", "pagamento_fatura"}:
        _append_extrato_metadados(
            month_dir,
            {
                "tipo": metadata_kind,
                "descricao": description,
                "valor": abs(_parse_br_float(amount_token)),
                "fonte": fonte,
            },
        )
    logger.warning(
        "Linha tratada como metadado (%s) e não incluída: %s",
        metadata_kind,
        description[:80],
    )
    return metadata_kind


def _parse_extrato_from_words(
    words: list[dict[str, Any]],
    *,
    fonte: str,
    default_year: int,
    month_dir: Path | None,
) -> tuple[list[Transaction], int]:
    """
    Extrai transações do extrato por coordenadas XY.

    Layout esperado:
    - data DD/MM/YYYY na primeira word
    - descrição no meio
    - valor (com sinal) na última word antes da coluna de saldo
    - saldo em x0 >= _SALDO_X_MIN (ignorado)
    """
    filtered_words = [word for word in words if float(word["x0"]) < _SALDO_X_MIN]
    lines = _group_words_by_line(filtered_words)
    transactions: list[Transaction] = []
    filtered_metadata_lines = 0

    for line_top in sorted(lines):
        line_words = lines[line_top]
        texts = [str(word["text"]).strip() for word in line_words if str(word.get("text", "")).strip()]
        if len(texts) < 3:
            continue
        if not _RE_DATE_FULL.match(texts[0]):
            continue
        if not _RE_AMOUNT.match(texts[-1]):
            continue

        date_token = texts[0]
        amount_token = texts[-1]
        description = " ".join(texts[1:-1]).strip()
        if not description:
            continue

        metadata_kind = _handle_metadata_line(
            description,
            amount_token,
            fonte=fonte,
            month_dir=month_dir,
        )
        if metadata_kind:
            filtered_metadata_lines += 1
            continue

        transaction_date = _parse_extrato_date(date_token, default_year)
        if transaction_date is None:
            logger.warning("Data inválida ignorada no extrato (%s): %s", fonte, date_token)
            continue

        valor_numerico = _parse_br_float(amount_token)
        if valor_numerico == 0:
            logger.warning("Valor zero ignorado no extrato: %s %s", date_token, description[:80])
            continue

        transaction = Transaction(
            data=transaction_date,
            descricao_original=description,
            valor=abs(valor_numerico),
            tipo="credito" if valor_numerico > 0 else "debito",
            meio="debito_pix",
            fonte=fonte,
            cartao_final=None,
            parcela_info=None,
            classificacao=Classificacao(metodo="pendente", confianca=0.0),
            metadados=None,
        )
        transactions.append(transaction)

    return transactions, filtered_metadata_lines


def try_parse_extrato_line(
    line: str,
    *,
    fonte: str,
    default_year: int,
    month_dir: Path | None = None,
) -> tuple[Transaction | None, str | None]:
    """
    Função legada: interpreta linha textual de extrato.

    Retorna (transação, kind_metadado). Quando kind_metadado não é None, a linha
    é tratada como metadado e não vira transação.
    """
    stripped = line.strip()
    match = _RE_EXTRATO_LINE.match(stripped)
    if not match:
        return None, None

    date_token, description, amount_token = match.groups()
    metadata_kind = _handle_metadata_line(
        description.strip(),
        amount_token,
        fonte=fonte,
        month_dir=month_dir,
    )
    if metadata_kind:
        return None, metadata_kind

    transaction_date = _parse_extrato_date(date_token, default_year)
    if transaction_date is None:
        logger.warning(
            "Data inválida ignorada no extrato (%s): %s",
            fonte,
            stripped[:120],
        )
        return None, None

    valor_numerico = _parse_br_float(amount_token)
    if valor_numerico == 0:
        logger.warning("Valor zero ignorado no extrato: %s", stripped[:120])
        return None, None

    transaction = Transaction(
        data=transaction_date,
        descricao_original=description.strip(),
        valor=abs(valor_numerico),
        tipo="credito" if valor_numerico > 0 else "debito",
        meio="debito_pix",
        fonte=fonte,
        cartao_final=None,
        parcela_info=None,
        classificacao=Classificacao(metodo="pendente", confianca=0.0),
        metadados=None,
    )
    return transaction, None


class ItauExtratoParser(BaseParser):
    """Parser de extrato de conta corrente Itaú usando coordenadas XY."""

    def __init__(self, fonte: str, default_year: int | None = None) -> None:
        self.fonte = fonte
        self.default_year = default_year
        self.filtered_metadata_lines = 0

    def parse(self, filepath: Path) -> list[Transaction]:
        return self.parse_with_options(filepath, month_dir=None, use_fallback=False)

    def parse_with_options(
        self,
        filepath: Path,
        *,
        month_dir: Path | None,
        use_fallback: bool,
    ) -> list[Transaction]:
        del use_fallback  # Compatibilidade de assinatura; fluxo atual não usa fallback.
        year = self.default_year if self.default_year is not None else date.today().year
        transactions: list[Transaction] = []
        self.filtered_metadata_lines = 0

        with pdfplumber.open(str(filepath)) as pdf:
            for page in pdf.pages:
                words = page.extract_words(keep_blank_chars=False) or []
                if not words:
                    continue
                page_transactions, page_filtered = _parse_extrato_from_words(
                    words,
                    fonte=self.fonte,
                    default_year=year,
                    month_dir=month_dir,
                )
                transactions.extend(page_transactions)
                self.filtered_metadata_lines += page_filtered

        logger.info(
            "Extrato parseado (%s): %d transações, %d linhas de metadado filtradas",
            self.fonte,
            len(transactions),
            self.filtered_metadata_lines,
        )
        return transactions
