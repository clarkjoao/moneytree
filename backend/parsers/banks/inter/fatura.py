from __future__ import annotations

import json
import logging
import re
from datetime import date
from pathlib import Path
from typing import Any

from markitdown import MarkItDown

from backend.models.transaction import Classificacao, ParcelaInfo, Transaction
from backend.parsers.base_parser import BaseParser

logger = logging.getLogger(__name__)

_MESES = {
    "jan": 1,
    "fev": 2,
    "mar": 3,
    "abr": 4,
    "mai": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "set": 9,
    "out": 10,
    "nov": 11,
    "dez": 12,
}

_RE_CARD_HEADER = re.compile(r"CART[ÃA]O\s+(\d{4}\*{4}\d{4})", re.IGNORECASE)
_RE_TABLE_ROW = re.compile(
    r"^\|\s*(\d{2}\s+de\s+\w+\.?\s+\d{4})\s*\|"
    r"\s*(.+?)\s*\|"
    r"(?:\s*-?\s*\|)+"
    r"\s*(\+?\s*R\$\s*[\d.,]+)\s*\|"
)
_RE_PLAIN_ROW = re.compile(
    r"^(\d{2}\s+de\s+\w+\.?\s+\d{4})"
    r"\s+(.+?)"
    r"\s+-\s+"
    r"(R\$\s*[\d.,]+)\s*$"
)
_RE_PARCELA = re.compile(r"\(Parcela\s+(\d+)\s+de\s+(\d+)\)", re.IGNORECASE)


def _append_extrato_metadados(month_dir: Path, record: dict[str, Any]) -> None:
    month_dir.mkdir(parents=True, exist_ok=True)
    path = month_dir / "extrato_metadados.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _parse_inter_date(raw: str) -> date | None:
    parts = raw.lower().replace(".", "").split()
    try:
        day = int(parts[0])
        month = _MESES.get(parts[2][:3])
        year = int(parts[3])
        if not month:
            return None
        return date(year, month, day)
    except (IndexError, ValueError):
        return None


def _parse_inter_value(raw: str) -> tuple[float, bool]:
    is_credit = raw.strip().startswith("+")
    raw_digits = re.sub(r"[^\d,]", "", raw)
    if not raw_digits:
        return 0.0, is_credit
    value = float(raw_digits.replace(",", "."))
    return value, is_credit


def _is_structural(line: str) -> bool:
    stripped_line = line.strip()
    upper_line = stripped_line.upper()
    return (
        not stripped_line
        or stripped_line.startswith("| ---")
        or stripped_line.startswith("| Data")
        or "TOTAL CARTÃO" in upper_line
        or "TOTAL CARTAO" in upper_line
        or stripped_line == "Despesas da fatura"
        or re.match(r"^[A-Z\s]{10,}$", stripped_line) is not None
        or ("****" in stripped_line and "CARTÃO" not in upper_line and "CARTAO" not in upper_line)
    )


def _is_metadado(movimentacao: str) -> bool:
    upper = movimentacao.upper().strip()
    return "PAGAMENTO DE FATURA" in upper


def _extract_parcela_info(movimentacao: str) -> tuple[str, ParcelaInfo | None]:
    match = _RE_PARCELA.search(movimentacao)
    if not match:
        return movimentacao.strip(), None
    parcela_info = ParcelaInfo(numero=int(match.group(1)), total=int(match.group(2)))
    descricao_limpa = _RE_PARCELA.sub("", movimentacao).strip()
    return descricao_limpa, parcela_info


def _parse_table_row(line: str) -> tuple[str, str, str] | None:
    match = _RE_TABLE_ROW.match(line.strip())
    if not match:
        return None
    return match.group(1), match.group(2), match.group(3)


def _parse_plain_row(line: str) -> tuple[str, str, str] | None:
    match = _RE_PLAIN_ROW.match(line.strip())
    if not match:
        return None
    return match.group(1), match.group(2), match.group(3)


class InterFaturaParser(BaseParser):
    def __init__(self, fonte: str, default_year: int | None = None) -> None:
        self.fonte = fonte
        self.default_year = default_year
        self._metadados_filtrados = 0

    def parse(self, filepath: Path) -> list[Transaction]:
        return self.parse_with_options(filepath, month_dir=None)

    def parse_with_options(
        self,
        filepath: Path,
        *,
        month_dir: Path | None,
        use_fallback: bool = False,
    ) -> list[Transaction]:
        del use_fallback
        source_name = filepath.stem
        transactions: list[Transaction] = []
        self._metadados_filtrados = 0
        cartao_ativo: str | None = None

        try:
            markdown_result = MarkItDown().convert(str(filepath))
            text_content = markdown_result.text_content or ""
        except Exception:
            logger.warning("Falha ao extrair texto com MarkItDown (%s)", filepath.name, exc_info=True)
            return transactions

        for raw_line in text_content.splitlines():
            line = raw_line.strip()
            card_match = _RE_CARD_HEADER.search(line)
            if card_match:
                cartao_ativo = card_match.group(1)[-4:]
                continue

            if _is_structural(line):
                continue

            parsed_row = _parse_table_row(line)
            if parsed_row is None:
                parsed_row = _parse_plain_row(line)
            if parsed_row is None:
                continue

            raw_date, movimentacao, raw_value = parsed_row
            parsed_date = _parse_inter_date(raw_date)
            if parsed_date is None:
                logger.warning("Data inválida na fatura Inter (%s): %s", filepath.name, line[:80])
                continue

            try:
                value, is_credit = _parse_inter_value(raw_value)
            except ValueError:
                logger.warning("Valor inválido na fatura Inter (%s): %s", filepath.name, line[:80])
                continue
            if value == 0:
                logger.warning("Valor zero detectado na fatura Inter (%s): %s", filepath.name, line[:80])
                continue

            if _is_metadado(movimentacao):
                self._metadados_filtrados += 1
                if is_credit and month_dir is not None:
                    _append_extrato_metadados(
                        month_dir,
                        {
                            "tipo": "pagamento_fatura",
                            "descricao": movimentacao,
                            "valor": value,
                            "fonte": source_name,
                        },
                    )
                logger.warning("Linha tratada como metadado na fatura Inter (%s): %s", filepath.name, line[:80])
                continue

            descricao_limpa, parcela_info = _extract_parcela_info(movimentacao)
            transactions.append(
                Transaction(
                    data=parsed_date,
                    descricao_original=descricao_limpa,
                    valor=value,
                    tipo="debito",
                    meio="cartao_credito",
                    fonte=source_name,
                    cartao_final=cartao_ativo,
                    parcela_info=parcela_info,
                    classificacao=Classificacao(metodo="pendente", confianca=0.0),
                    metadados=None,
                )
            )

        logger.info(
            "Fatura Inter parseada (%s): %d transações, %d metadados filtrados",
            self.fonte,
            len(transactions),
            self._metadados_filtrados,
        )
        return transactions
