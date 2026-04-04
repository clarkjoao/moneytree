from __future__ import annotations

import logging
import re
from calendar import monthrange
from datetime import date
from pathlib import Path

import pdfplumber

from models.transaction import Classificacao, ParcelaInfo, Transaction
from parsers.base_parser import BaseParser
from parsers.banks.itau.markitdown_fallback import record_unparsed_page

logger = logging.getLogger(__name__)

_RE_AMOUNT_BR = re.compile(r"(-?)\s*([\d]{1,3}(?:\.[\d]{3})*,\d{2}|\d+,\d{2})\s*$")
_RE_DATE_HEAD = re.compile(
    r"^(\d{2})/(\d{2})(?:/(\d{2,4}))?\s+(.+)$",
)
_RE_PARCEL = re.compile(r"\b(\d{1,2})/(\d{1,2})\b")
_RE_CARD_FINAL = re.compile(
    r"(?:final|cart[aã]o)\s*[:\s]*(\d{4})|(\d{4})\s*[-–]\s*mastercard",
    re.IGNORECASE,
)
_RE_INTERNATIONAL = re.compile(
    r"(USD|EUR|GBP)\s*[\d.,]+\s*(?:\(|\[)?\s*R\$\s*([\d]{1,3}(?:\.[\d]{3})*,\d{2}|\d+,\d{2})",
    re.IGNORECASE,
)
_RE_IGNORE_SECTION = re.compile(
    r"compras\s+parceladas.*pr[oó]xim(?:a|as)\s+faturas",
    re.IGNORECASE,
)


def _parse_br_float(amount_token: str) -> float:
    normalized = amount_token.replace(".", "").replace(",", ".")
    return float(normalized)


def _resolve_year(month: int, year_two_or_four: int | None, default_year: int) -> int:
    if year_two_or_four is None:
        return default_year
    if year_two_or_four < 100:
        return 2000 + year_two_or_four
    return year_two_or_four


def _safe_date(day: int, month: int, year: int) -> date | None:
    last = monthrange(year, month)[1]
    if day > last:
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _extract_parcel_info(description: str, day: int, month: int) -> ParcelaInfo | None:
    for match in _RE_PARCEL.finditer(description):
        first, second = int(match.group(1)), int(match.group(2))
        if first == day and second == month:
            continue
        if second >= 1 and second <= 60 and first >= 1 and first <= second:
            return ParcelaInfo(numero=first, total=second)
    return None


def _current_card_from_text(block: str) -> str | None:
    match = _RE_CARD_FINAL.search(block)
    if not match:
        return None
    return match.group(1) or match.group(2)


def _is_probable_resume_after_parceladas_section(stripped: str) -> bool:
    if not _RE_DATE_HEAD.match(stripped):
        return False
    if not _RE_AMOUNT_BR.search(stripped):
        return False
    if re.search(r"pr[oó]xim", stripped, re.IGNORECASE):
        return False
    return True


def parse_fatura_line_for_tests(
    line: str,
    *,
    default_year: int,
    fonte: str,
    cartao_final: str | None,
) -> Transaction | None:
    """Expõe o parser de linha para testes (mesma lógica interna de `_parse_line_to_transaction`)."""
    return _parse_line_to_transaction(
        line,
        default_year=default_year,
        fonte=fonte,
        cartao_final=cartao_final,
    )


def _parse_line_to_transaction(
    line: str,
    *,
    default_year: int,
    fonte: str,
    cartao_final: str | None,
) -> Transaction | None:
    stripped = line.strip()
    if not stripped:
        return None
    upper = stripped.upper()
    if upper.startswith("PAGAMENTO EFETUADO"):
        return None

    date_match = _RE_DATE_HEAD.match(stripped)
    if not date_match:
        return None

    day_s, month_s, year_s, rest = date_match.groups()
    day, month = int(day_s), int(month_s)
    year = _resolve_year(month, int(year_s) if year_s else None, default_year)
    transaction_date = _safe_date(day, month, year)
    if transaction_date is None:
        logger.warning("Data inválida ignorada na fatura (%s): %s", fonte, stripped[:120])
        return None

    amount_match = _RE_AMOUNT_BR.search(rest)
    if not amount_match:
        return None

    sign, amount_raw = amount_match.group(1), amount_match.group(2)
    description = rest[: amount_match.start()].strip()
    valor_absoluto = abs(_parse_br_float(amount_raw))

    international = _RE_INTERNATIONAL.search(stripped)
    metadados: dict | None = None
    if international:
        metadados = {
            "moeda_original": international.group(1).upper(),
            "valor_brl_fatura": amount_raw,
        }

    is_credit = sign == "-" or "DESC " in upper or "ESTORNO" in upper or "CRÉDITO" in upper
    tipo = "credito" if is_credit else "debito"

    parcela_info = _extract_parcel_info(description, day, month)

    compromisso: str | None = "parcela" if parcela_info else "a_vista"

    return Transaction(
        data=transaction_date,
        descricao_original=description or stripped,
        valor=valor_absoluto,
        tipo=tipo,
        meio="cartao_credito",
        fonte=fonte,
        cartao_final=cartao_final,
        parcela_info=parcela_info,
        classificacao=Classificacao(
            compromisso=compromisso,
            metodo="pendente",
            confianca=0.0,
        ),
        metadados=metadados,
    )


def _page_needs_fallback(page: pdfplumber.page.Page, parsed_count_for_page: int) -> bool:
    text = page.extract_text(layout=False) or ""
    stripped = text.strip()
    if len(stripped) < 80:
        return False
    tables = page.extract_tables() or []
    has_table = any(table for table in tables if table)
    if has_table and parsed_count_for_page == 0:
        return True
    if not has_table and parsed_count_for_page == 0 and len(stripped) > 200:
        return True
    return False


class ItauFaturaParser(BaseParser):
    """Parser de fatura Mastercard Itaú a partir de texto extraído com pdfplumber."""

    def __init__(self, fonte: str, default_year: int | None = None) -> None:
        self.fonte = fonte
        self.default_year = default_year
        self.filtered_lines = 0

    def parse(self, filepath: Path) -> list[Transaction]:
        return self.parse_with_options(filepath, month_dir=None, use_fallback=False)

    def parse_with_options(
        self,
        filepath: Path,
        *,
        month_dir: Path | None,
        use_fallback: bool,
    ) -> list[Transaction]:
        year = self.default_year if self.default_year is not None else date.today().year
        transactions: list[Transaction] = []
        skip_parceladas = False
        current_card: str | None = None
        page_counts: dict[int, int] = {}
        self.filtered_lines = 0

        with pdfplumber.open(str(filepath)) as pdf:
            for page_index, page in enumerate(pdf.pages):
                text = page.extract_text(layout=False) or ""
                card_hint = _current_card_from_text(text)
                if card_hint:
                    current_card = card_hint

                for raw_line in text.splitlines():
                    stripped = raw_line.strip()
                    card_from_line = _current_card_from_text(raw_line)
                    if card_from_line:
                        current_card = card_from_line

                    if skip_parceladas:
                        if _is_probable_resume_after_parceladas_section(stripped):
                            skip_parceladas = False
                        else:
                            self.filtered_lines += 1
                            continue

                    if _RE_IGNORE_SECTION.search(stripped):
                        skip_parceladas = True
                        self.filtered_lines += 1
                        continue

                    upper_line = stripped.upper()
                    if upper_line.startswith("PAGAMENTO EFETUADO"):
                        self.filtered_lines += 1
                        continue

                    transaction = _parse_line_to_transaction(
                        raw_line,
                        default_year=year,
                        fonte=self.fonte,
                        cartao_final=current_card,
                    )
                    if transaction:
                        transactions.append(transaction)
                        page_counts[page_index] = page_counts.get(page_index, 0) + 1

                if use_fallback and month_dir is not None:
                    if _page_needs_fallback(page, page_counts.get(page_index, 0)):
                        try:
                            record_unparsed_page(month_dir, filepath, page_index)
                        except Exception:
                            logger.exception(
                                "Fallback MarkItDown falhou para página %s de %s",
                                page_index + 1,
                                filepath.name,
                            )

        return transactions
