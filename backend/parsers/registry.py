from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

import pdfplumber

from backend.parsers.base_parser import BaseParser
from backend.parsers.banks.itau.extrato import ItauExtratoParser
from backend.parsers.banks.itau.fatura import ItauFaturaParser

logger = logging.getLogger(__name__)

Bucket = Literal["fatura", "extrato"]

ParserFactory = Callable[[str, int | None], BaseParser]


@dataclass(frozen=True)
class ResolvedParser:
    bucket: Bucket
    create: ParserFactory


def _first_page_text_upper(pdf_path: Path) -> str:
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            if not pdf.pages:
                return ""
            text = pdf.pages[0].extract_text(layout=False) or ""
            return text.upper()
    except Exception:
        logger.warning("Não foi possível ler fingerprint de %s", pdf_path.name, exc_info=True)
        return ""


def _filename_itau_fatura(name_upper: str) -> bool:
    if name_upper.startswith("FATURA_MASTERCARD"):
        return True
    return "FATURA" in name_upper and "MASTERCARD" in name_upper


def _filename_itau_extrato(name_upper: str) -> bool:
    return name_upper.startswith("ITAU_EXTRATO") or "ITAU_EXTRATO" in name_upper


def _text_suggests_itau(text_upper: str) -> bool:
    return "ITAU" in text_upper or "ITAÚ" in text_upper


def _fingerprint_itau_fatura(text_upper: str) -> bool:
    if not text_upper:
        return False
    if not _text_suggests_itau(text_upper):
        return False
    if "MASTERCARD" in text_upper and ("FATURA" in text_upper or "CARTÃO" in text_upper or "CARTAO" in text_upper):
        return True
    return False


def _fingerprint_itau_extrato(text_upper: str) -> bool:
    if not text_upper:
        return False
    if "EXTRATO" not in text_upper:
        return False
    return _text_suggests_itau(text_upper) or "CONTA CORRENTE" in text_upper


_REGISTRY: list[tuple[Callable[[str], bool], Callable[[str], bool], Bucket, ParserFactory]] = [
    (_filename_itau_fatura, _fingerprint_itau_fatura, "fatura", ItauFaturaParser),
    (_filename_itau_extrato, _fingerprint_itau_extrato, "extrato", ItauExtratoParser),
]


def resolve_parser_for_pdf(pdf_path: Path) -> ResolvedParser | None:
    """
    Escolhe o parser adequado pelo nome do arquivo; se inconclusivo, usa a primeira página.
    """
    name_upper = pdf_path.name.upper()
    for filename_hit, fingerprint_hit, bucket, factory in _REGISTRY:
        if filename_hit(name_upper):
            return ResolvedParser(bucket=bucket, create=factory)

    text_upper = _first_page_text_upper(pdf_path)
    for _filename_hit, fingerprint_hit, bucket, factory in _REGISTRY:
        if fingerprint_hit(text_upper):
            logger.info("Parser resolvido por fingerprint: %s → %s", pdf_path.name, bucket)
            return ResolvedParser(bucket=bucket, create=factory)

    return None
