from __future__ import annotations

import logging
import re
from calendar import monthrange
from datetime import date
from pathlib import Path

import pdfplumber

from backend.models.transaction import Classificacao, ParcelaInfo, Transaction
from backend.parsers.base_parser import BaseParser
from backend.parsers.banks.itau.markitdown_fallback import record_unparsed_page
from backend.parsers.banks.itau._utils import _group_words_by_line as _group_words_by_line_shared

logger = logging.getLogger(__name__)


def _group_words_by_line(
    words: list[dict],
    tolerance: float = 3.0,
) -> dict[float, list[dict]]:
    """
    Wrapper para compatibilidade com parser word-based.

    Mantém função disponível neste módulo para reduzir impacto em migrações.
    """
    return {
        top: [dict(word) for word in line_words]
        for top, line_words in _group_words_by_line_shared(words, tolerance).items()
    }

# Coluna esquerda da página (lançamentos atuais); deixa espaço suficiente
# para capturar o valor final sem encostar na coluna direita.
_LEFT_COL_RATIO = 0.55

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
_RE_PAYMENT_LINE = re.compile(r"^\d{2}/\d{2}\s+PAGAMENTO\s*EFETUADO", re.IGNORECASE)

_RE_METADADO_LIMITE = re.compile(
    r"limite\s*(total|disponível|utilizado|máximo|de\s*cr[eé]dito|de\s*saque)|"
    r"encargos?\s*cobrados|"
    r"juros\s*(de\s*mora|da\s*compra)|"
    r"multa\s*por\s*atraso|"
    r"iof\s*de\s*financiamento|"
    r"valor\s*(total\s*financiado|solicitado|do\s*iof)|"
    r"parcelas?\s*fixas|"
    r"pagamento\s*m[ií]nimo|"
    r"d[oó]lar\s*de\s*convers[aã]o|"
    r"fique\s*atento|"
    r"novo\s*teto\s*de\s*juros",
    re.IGNORECASE,
)

_RE_SECTION_HEADER = re.compile(
    r"^(data\s+estabelecimento|lançamentos[:\s]|compras\s+parceladas|"
    r"saúde\s*\.|vestuário\s*\.|alimentação\s*\.|veículos\s*\.|"
    r"diversos\s*\.|serviços\s*\.|lazer\s*\.)",
    re.IGNORECASE,
)

_RE_FUSED_LINE = re.compile(
    r"^(.+?)\s+(\d{1,3}(?:\.\d{3})*,\d{2})\s+(\d{2}/\d{2})\s+([A-Z0-9].*)$"
)


def _extract_left_column_lines(page: pdfplumber.page.Page) -> list[str]:
    """
    Reconstrói linhas da coluna esquerda via coordenadas XY.

    `extract_text()` perde separadores e centavos em alguns PDFs do Itaú.
    Usar `extract_words()` preserva os tokens e ainda evita mistura com
    a coluna direita quando limitado ao `x0` da coluna válida.
    """
    words = page.extract_words(use_text_flow=True, keep_blank_chars=False) or []
    left_words = [word for word in words if float(word["x0"]) < page.width * _LEFT_COL_RATIO]
    lines = _group_words_by_line(left_words)
    return [
        " ".join(str(word["text"]).strip() for word in lines[top] if str(word.get("text", "")).strip())
        for top in sorted(lines)
    ]


def _split_fused_line(line: str) -> list[str]:
    """
    Detecta e separa linhas onde duas transações foram fundidas.

    Conservador: o crop da coluna esquerda resolve a maioria dos casos;
    não faz split agressivo para evitar falsos positivos.
    """
    stripped = line.strip()
    if re.match(r"^\d{2}/\d{2}", stripped):
        return [line]
    if _RE_FUSED_LINE.match(stripped):
        logger.debug("Linha com padrão de fusão (não dividida): %s", stripped[:120])
    return [line]


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


_RE_SUSPICIOUS = re.compile(
    r"\d{1,3}(?:\.\d{3})*,\d{2}\s+\d{2}/\d{2}\s+[A-Z]",
)


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
    if upper.startswith("PAGAMENTO EFETUADO") or _RE_PAYMENT_LINE.match(stripped):
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
    if valor_absoluto <= 0:
        logger.debug("Linha com valor zero ignorada na fatura (%s): %s", fonte, stripped[:120])
        return None

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
                full_text = page.extract_text(layout=False) or ""
                card_hint = _current_card_from_text(full_text)
                if card_hint:
                    current_card = card_hint

                for raw_line in _extract_left_column_lines(page):
                    for segment in _split_fused_line(raw_line):
                        stripped = segment.strip()
                        if not stripped:
                            continue

                        card_from_line = _current_card_from_text(segment)
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

                        if _RE_METADADO_LIMITE.search(stripped):
                            self.filtered_lines += 1
                            continue

                        if _RE_SECTION_HEADER.match(stripped):
                            self.filtered_lines += 1
                            continue

                        upper_line = stripped.upper()
                        if upper_line.startswith("PAGAMENTO EFETUADO") or _RE_PAYMENT_LINE.match(stripped):
                            self.filtered_lines += 1
                            continue

                        transaction = _parse_line_to_transaction(
                            segment,
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

        suspicious = [
            tx
            for tx in transactions
            if _RE_SUSPICIOUS.search(tx.descricao_original)
            or "limite" in tx.descricao_original.lower()
            or tx.valor > 10000
        ]
        if suspicious:
            logger.warning(
                "Parse (%s): %d transação(ões) com descrição suspeita de fusão de colunas:",
                self.fonte,
                len(suspicious),
            )
            for tx in suspicious:
                logger.warning("  val=%.2f desc=%s", tx.valor, tx.descricao_original[:80])

        return transactions
