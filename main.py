from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analyzer.anomaly import detect_anomalies
from analyzer.metrics import compute_month
from analyzer.report import print_metrics_tabular, write_month_report
from classifier.pipeline import run_classify_month
from classifier.review import apply_review_csv, open_csv_for_editing, write_review_csv
from transaction_store import load_month_transactions
from models.transaction import Transaction
from parsers.registry import resolve_parser_for_pdf

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("moneytree")

_RE_MONTH_IN_NAME = re.compile(r"(20\d{2})-(\d{2})")


def detect_month_key(filename: str) -> str:
    match = _RE_MONTH_IN_NAME.search(filename)
    if match:
        year, month = match.group(1), match.group(2)
        return f"{year}-{month}"
    from datetime import date

    today = date.today()
    logger.warning(
        "Mês não encontrado no nome do arquivo %s; usando %04d-%02d",
        filename,
        today.year,
        today.month,
    )
    return f"{today.year:04d}-{today.month:02d}"


def default_year_from_month_key(month_key: str) -> int:
    try:
        year_part = int(month_key.split("-")[0])
        return year_part
    except (IndexError, ValueError):
        from datetime import date

        return date.today().year


def write_transactions_json(path: Path, transactions: list[Transaction]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [transaction.model_dump(mode="json") for transaction in transactions]
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def parse_command(input_dir: Path, use_fallback: bool) -> int:
    raw_path = input_dir.resolve()
    if not raw_path.is_dir():
        logger.error("Pasta de entrada inválida: %s", raw_path)
        return 1

    processed_root = ROOT / "data" / "processed"
    by_month_fatura: dict[str, list[Transaction]] = defaultdict(list)
    by_month_extrato: dict[str, list[Transaction]] = defaultdict(list)
    files_seen = 0
    skipped_files = 0
    total_filtered_lines = 0

    for pdf_path in sorted(raw_path.glob("*.pdf")):
        resolved = resolve_parser_for_pdf(pdf_path)
        if resolved is None:
            logger.warning("Nenhum parser para o PDF (ignorado): %s", pdf_path.name)
            skipped_files += 1
            continue
        files_seen += 1
        month_key = detect_month_key(pdf_path.name)
        month_dir = processed_root / month_key
        default_year = default_year_from_month_key(month_key)

        if resolved.bucket == "fatura":
            fonte = f"fatura_mastercard_{month_key}"
        else:
            fonte = f"extrato_{month_key}"

        parser = resolved.create(fonte, default_year)
        items = parser.parse_with_options(
            pdf_path,
            month_dir=month_dir,
            use_fallback=use_fallback,
        )
        if resolved.bucket == "fatura":
            total_filtered_lines += getattr(parser, "filtered_lines", 0)
            by_month_fatura[month_key].extend(items)
        else:
            total_filtered_lines += getattr(parser, "filtered_metadata_lines", 0)
            by_month_extrato[month_key].extend(items)

    total_transactions = 0
    for month_key in sorted(set(by_month_fatura) | set(by_month_extrato)):
        month_dir = processed_root / month_key
        month_dir.mkdir(parents=True, exist_ok=True)

        fatura_list = by_month_fatura.get(month_key, [])
        extrato_list = by_month_extrato.get(month_key, [])

        if fatura_list:
            write_transactions_json(month_dir / "fatura.json", fatura_list)
        if extrato_list:
            write_transactions_json(month_dir / "extrato.json", extrato_list)

        combined = fatura_list + extrato_list
        total_transactions += len(combined)

    logger.info("Arquivos PDF reconhecidos: %s (ignorados: %s)", files_seen, skipped_files)
    logger.info("Total de transações extraídas: %s", total_transactions)
    logger.info("Linhas filtradas (metadado / ignoradas na fatura): %s", total_filtered_lines)
    logger.info(
        "Classificação: use `python main.py classify --mes YYYY-MM` (JSON base permanece sem regras)."
    )
    return 0


def classify_command(month_key: str, config_dir: Path, use_llm: bool) -> int:
    stats = run_classify_month(ROOT, month_key, config_dir, use_llm=use_llm)
    logger.info("Total transações: %s", stats["total"])
    logger.info("Classificadas por regra: %s", stats["por_regra"])
    logger.info("Contexto atualizado em: %s", stats["contexto_touch"])
    logger.info("Classificadas por LLM (linhas): %s", stats["por_llm"])
    logger.info("Lotes LLM com falha: %s", stats["lotes_llm_falhos"])
    logger.info("Pendentes / baixa confiança (revisão): %s", stats["revisao"])
    return 0


def review_command(month_key: str) -> int:
    processed_root = ROOT / "data" / "processed"
    transactions = load_month_transactions(processed_root, month_key)
    if not transactions:
        logger.error("Sem transações para o mês %s", month_key)
        return 1
    month_dir = processed_root / month_key
    csv_path = write_review_csv(month_dir, transactions)
    open_csv_for_editing(csv_path)
    return 0


def apply_review_command(month_key: str, config_dir: Path) -> int:
    processed_root = ROOT / "data" / "processed"
    month_dir = processed_root / month_key
    csv_path = month_dir / "review.csv"
    regras_path = config_dir / "regras.json"
    apply_review_csv(month_dir, month_key, csv_path, regras_path, processed_root)
    return 0


def analyze_command(month_key: str, only_metrics: bool) -> int:
    metrics = compute_month(month_key, project_root=ROOT)
    if only_metrics:
        print_metrics_tabular(metrics)
        return 0
    anomalies = detect_anomalies(month_key, metrics, project_root=ROOT)
    report_path = write_month_report(ROOT, metrics, anomalies)
    logger.info("Relatório: %s", report_path)
    logger.info("Métricas JSON: data/processed/%s/metrics_%s.json", month_key, month_key)
    print()
    print_metrics_tabular(metrics)
    print()
    if anomalies:
        print("Anomalias:")
        for item in anomalies:
            print(f"  - [{item.tipo}] {item.descricao}")
    else:
        print("Anomalias: nenhuma detectada.")
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="moneytree", description="MoneyTree CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    parse_parser = sub.add_parser("parse", help="Processa PDFs em data/raw")
    parse_parser.add_argument(
        "--input",
        type=Path,
        default=ROOT / "data" / "raw",
        help="Pasta com PDFs (padrão: ./data/raw/)",
    )
    parse_parser.add_argument(
        "--fallback-markitdown",
        action="store_true",
        help="Ativa MarkItDown para páginas sem estrutura detectável",
    )

    classify_parser = sub.add_parser("classify", help="Pipeline de classificação para um mês")
    classify_parser.add_argument("--mes", required=True, help="YYYY-MM")
    classify_parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "config",
        help="Pasta com regras.json, perfil.json, taxonomia.json",
    )
    classify_parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Pula a etapa LLM (regras + contexto + recorrência + review)",
    )

    review_parser = sub.add_parser("review", help="Regenera e abre review.csv")
    review_parser.add_argument("--mes", required=True, help="YYYY-MM")

    apply_review_parser = sub.add_parser("apply-review", help="Aplica confirmações do CSV e aprende regras")
    apply_review_parser.add_argument("--mes", required=True, help="YYYY-MM")
    apply_review_parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "config",
        help="Pasta com regras.json",
    )

    analyze_parser = sub.add_parser("analyze", help="Métricas, anomalias e relatório Markdown")
    analyze_parser.add_argument("--mes", required=True, help="YYYY-MM")
    analyze_parser.add_argument(
        "--only-metrics",
        action="store_true",
        help="Só imprime métricas no terminal (sem gerar report/metrics JSON)",
    )

    return parser


def main() -> None:
    argument_parser = build_arg_parser()
    arguments = argument_parser.parse_args()
    if arguments.command == "parse":
        raise SystemExit(
            parse_command(
                arguments.input,
                use_fallback=arguments.fallback_markitdown,
            )
        )
    if arguments.command == "classify":
        raise SystemExit(
            classify_command(
                arguments.mes,
                arguments.config,
                use_llm=not arguments.no_llm,
            )
        )
    if arguments.command == "review":
        raise SystemExit(review_command(arguments.mes))
    if arguments.command == "apply-review":
        raise SystemExit(apply_review_command(arguments.mes, arguments.config))
    if arguments.command == "analyze":
        raise SystemExit(analyze_command(arguments.mes, arguments.only_metrics))
    raise SystemExit(1)


if __name__ == "__main__":
    main()
