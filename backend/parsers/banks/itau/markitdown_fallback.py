from __future__ import annotations

import logging
import tempfile
from datetime import datetime
from pathlib import Path

from pypdf import PdfReader, PdfWriter

logger = logging.getLogger(__name__)


def append_unparsed_markdown(
    month_dir: Path,
    source_pdf: Path,
    page_index_zero_based: int,
    markdown_chunk: str,
) -> Path:
    """Anexa trecho Markdown em `data/processed/{mes}/unparsed.md` para revisão manual."""
    month_dir.mkdir(parents=True, exist_ok=True)
    output_path = month_dir / "unparsed.md"
    stamp = datetime.now().isoformat(timespec="seconds")
    header = (
        f"\n\n---\n"
        f"<!-- fonte: {source_pdf.name} | página: {page_index_zero_based + 1} | {stamp} -->\n\n"
    )
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(header)
        handle.write(markdown_chunk.strip())
        handle.write("\n")
    logger.warning(
        "Página %s de %s enviada a unparsed.md (fallback MarkItDown)",
        page_index_zero_based + 1,
        source_pdf.name,
    )
    return output_path


def pdf_page_to_single_page_pdf(source_pdf: Path, page_index_zero_based: int) -> Path:
    reader = PdfReader(str(source_pdf))
    writer = PdfWriter()
    writer.add_page(reader.pages[page_index_zero_based])
    temporary_file = tempfile.NamedTemporaryFile(
        suffix=".pdf", delete=False, prefix="moneytree_page_"
    )
    temporary_path = Path(temporary_file.name)
    temporary_file.close()
    with temporary_path.open("wb") as handle:
        writer.write(handle)
    return temporary_path


def convert_pdf_page_to_markdown(source_pdf: Path, page_index_zero_based: int) -> str:
    """Converte uma única página do PDF para Markdown via MarkItDown."""
    from markitdown import MarkItDown

    single_page_pdf = pdf_page_to_single_page_pdf(source_pdf, page_index_zero_based)
    try:
        converter = MarkItDown()
        result = converter.convert(str(single_page_pdf))
        markdown = getattr(result, "markdown", None) or getattr(result, "text_content", None)
        return (markdown or "").strip()
    finally:
        single_page_pdf.unlink(missing_ok=True)


def record_unparsed_page(
    month_dir: Path,
    source_pdf: Path,
    page_index_zero_based: int,
) -> None:
    markdown_text = convert_pdf_page_to_markdown(source_pdf, page_index_zero_based)
    append_unparsed_markdown(month_dir, source_pdf, page_index_zero_based, markdown_text)
