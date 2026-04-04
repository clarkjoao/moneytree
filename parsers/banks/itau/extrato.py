from __future__ import annotations

import json
import logging
import re
from calendar import monthrange
from datetime import date
from pathlib import Path

import pdfplumber

from models.transaction import Classificacao, Transaction
from parsers.base_parser import BaseParser
from parsers.banks.itau.markitdown_fallback import record_unparsed_page

logger = logging.getLogger(__name__)

_RE_EXTRATO_LINE = re.compile(
    r"^(\d{2}/\d{2}(?:/\d{4})?)\s+(.+?)\s+"
    r"(-?[\d]{1,3}(?:\.[\d]{3})*,\d{2}|-?\d+,\d{2})\s*$",
)


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
    return None


def try_parse_extrato_line(
    line: str,
    *,
    fonte: str,
    default_year: int,
    month_dir: Path | None = None,
) -> tuple[Transaction | None, str | None]:
    """
    Interpreta uma linha de extrato. Retorna (transação, kind_metadado).
    Quando kind_metadado não é None, a linha não vira transação.
    """
    stripped = line.strip()
    match = _RE_EXTRATO_LINE.match(stripped)
    if not match:
        return None, None

    date_token, description, amount_token = match.groups()
    description_upper = description.strip().upper()
    metadata_kind = extrato_metadata_kind(description_upper)
    if metadata_kind:
        valor_bruto = abs(_parse_br_float(amount_token.replace("-", "")))
        if month_dir is not None and metadata_kind == "rendimento_aplicacao":
            _append_extrato_metadados(
                month_dir,
                {
                    "tipo": metadata_kind,
                    "descricao": description.strip(),
                    "valor": valor_bruto,
                    "fonte": fonte,
                },
            )
        logger.warning(
            "Linha tratada como metadado (%s) e não incluída: %s",
            metadata_kind,
            description.strip()[:80],
        )
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
    if valor_numerico > 0:
        tipo = "credito"
    elif valor_numerico < 0:
        tipo = "debito"
    else:
        logger.warning("Valor zero ignorado no extrato: %s", stripped[:120])
        return None, None

    transaction = Transaction(
        data=transaction_date,
        descricao_original=description.strip(),
        valor=abs(valor_numerico),
        tipo=tipo,
        meio="debito_pix",
        fonte=fonte,
        cartao_final=None,
        parcela_info=None,
        classificacao=Classificacao(metodo="pendente", confianca=0.0),
        metadados=None,
    )
    return transaction, None


def _append_extrato_metadados(month_dir: Path, record: dict) -> None:
    month_dir.mkdir(parents=True, exist_ok=True)
    path = month_dir / "extrato_metadados.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _page_needs_fallback(page: pdfplumber.page.Page, parsed_count_for_page: int) -> bool:
    text = page.extract_text(layout=False) or ""
    stripped = text.strip()
    if len(stripped) < 60:
        return False
    tables = page.extract_tables() or []
    has_table = any(table for table in tables if table)
    if has_table and parsed_count_for_page == 0:
        return True
    if not has_table and parsed_count_for_page == 0 and len(stripped) > 180:
        return True
    return False


class ItauExtratoParser(BaseParser):
    """Parser de extrato de conta corrente Itaú (texto via pdfplumber)."""

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
        year = self.default_year if self.default_year is not None else date.today().year
        transactions: list[Transaction] = []
        page_counts: dict[int, int] = {}
        self.filtered_metadata_lines = 0

        with pdfplumber.open(str(filepath)) as pdf:
            for page_index, page in enumerate(pdf.pages):
                text = page.extract_text(layout=False) or ""
                for raw_line in text.splitlines():
                    transaction, metadata_kind = try_parse_extrato_line(
                        raw_line,
                        fonte=self.fonte,
                        default_year=year,
                        month_dir=month_dir,
                    )
                    if metadata_kind is not None:
                        self.filtered_metadata_lines += 1
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
