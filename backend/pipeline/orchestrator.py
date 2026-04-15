from __future__ import annotations

import logging
import time
from collections import defaultdict
from pathlib import Path

from backend.pipeline.jobs import job_store

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
PROCESSED_ROOT = ROOT / "data" / "processed"
CONFIG_DIR = ROOT / "config"
RAW_DIR = ROOT / "data" / "raw"


def _step_start(job_id: str, step_name: str) -> float:
    started = time.time()
    job_store.update_step(job_id, step_name, status="running", started_at=started)
    return started


def _step_done(job_id: str, step_name: str, detail: str) -> None:
    job_store.update_step(
        job_id,
        step_name,
        status="done",
        detail=detail,
        finished_at=time.time(),
    )


def _step_error(job_id: str, step_name: str, error: str) -> None:
    job_store.update_step(
        job_id,
        step_name,
        status="error",
        error=error,
        finished_at=time.time(),
    )


def _update_step_detail(job_id: str, step_name: str, detail: str) -> None:
    job_store.update_step(job_id, step_name, detail=detail)


def run_parse(job_id: str, use_fallback: bool = False) -> dict:
    """
    Etapa 1: Lê os PDFs em data/raw/ e grava fatura.json / extrato.json.
    Retorna: { "mes": "2026-03" | None, "total_transactions": 87, "files_parsed": 2 }
    """
    from backend.cli import (
        default_year_from_month_key,
        detect_month_key,
        write_transactions_json,
    )
    from backend.models.transaction import dedupe_transactions
    from backend.parsers.registry import resolve_parser_for_pdf

    _step_start(job_id, "parse")
    try:
        by_month_fatura: dict[str, list] = defaultdict(list)
        by_month_extrato: dict[str, list] = defaultdict(list)
        files_seen = 0
        files = sorted(RAW_DIR.glob("*.pdf"))
        job_store.update_counters(
            job_id,
            files_total=len(files),
            files_processed=0,
            transactions_extracted=0,
        )

        for pdf_path in files:
            resolved = resolve_parser_for_pdf(pdf_path)
            if resolved is None:
                logger.warning("Nenhum parser para %s", pdf_path.name)
                job_store.update_counters(job_id, files_processed=files_seen)
                continue
            files_seen += 1
            month_key = detect_month_key(pdf_path.name)
            month_dir = PROCESSED_ROOT / month_key
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
                by_month_fatura[month_key].extend(items)
            else:
                by_month_extrato[month_key].extend(items)
            extracted_so_far = sum(len(items) for items in by_month_fatura.values()) + sum(
                len(items) for items in by_month_extrato.values()
            )
            job_store.update_job(job_id, mes=month_key)
            job_store.update_counters(
                job_id,
                files_processed=files_seen,
                transactions_extracted=extracted_so_far,
                transactions_total=extracted_so_far,
                transactions_pending=extracted_so_far,
            )
            _update_step_detail(
                job_id,
                "parse",
                f"{files_seen}/{len(files)} arquivo(s) · {extracted_so_far} transações extraídas",
            )

        total = 0
        detected_mes: str | None = None
        for month_key in sorted(set(by_month_fatura) | set(by_month_extrato)):
            month_dir = PROCESSED_ROOT / month_key
            month_dir.mkdir(parents=True, exist_ok=True)
            fatura_list = dedupe_transactions(by_month_fatura.get(month_key, []))
            extrato_list = dedupe_transactions(by_month_extrato.get(month_key, []))
            if fatura_list:
                write_transactions_json(month_dir / "fatura.json", fatura_list)
            if extrato_list:
                write_transactions_json(month_dir / "extrato.json", extrato_list)
            total += len(fatura_list) + len(extrato_list)
            detected_mes = month_key

        job_store.update_counters(
            job_id,
            files_processed=files_seen,
            transactions_extracted=total,
            transactions_total=total,
            transactions_pending=total,
        )
        detail = f"{total} transações extraídas de {files_seen} arquivo(s)"
        _step_done(job_id, "parse", detail)
        return {"mes": detected_mes, "total_transactions": total, "files_parsed": files_seen}

    except Exception as exc:
        _step_error(job_id, "parse", str(exc))
        raise


def run_classify(job_id: str, mes: str, use_llm: bool = True) -> dict:
    """
    Etapa 2: Aplica regras, contexto, LLM e grava classificacao_{mes}.json.
    Retorna: stats do run_classify_month
    """
    from backend.classifier.llm_config import build_llm_client_from_config
    from backend.classifier.pipeline import run_classify_month

    _step_start(job_id, "classify")
    try:
        llm_client = build_llm_client_from_config() if use_llm else None
        stats = run_classify_month(
            ROOT,
            mes,
            CONFIG_DIR,
            use_llm=use_llm,
            llm_client=llm_client,
            progress_callback=lambda payload: _on_classify_progress(job_id, payload),
        )
        por_regra = stats["por_regra"]
        por_llm = stats["por_llm"]
        revisao = stats["revisao"]
        total = stats["total"]
        pending = stats["pendentes_finais"]
        classified = stats["classificadas"]
        job_store.update_counters(
            job_id,
            transactions_total=total,
            transactions_classified=classified,
            transactions_pending=pending,
            transactions_review=revisao,
            llm_batches_failed=stats["lotes_llm_falhos"],
        )
        detail = (
            f"{total} transações · "
            f"{por_regra} por regra · "
            f"{por_llm} por LLM · "
            f"{pending} pendentes · "
            f"{revisao} para revisão"
        )
        _step_done(job_id, "classify", detail)
        return stats

    except Exception as exc:
        _step_error(job_id, "classify", str(exc))
        raise


def _on_classify_progress(job_id: str, payload: dict[str, int | str]) -> None:
    phase = str(payload.get("phase", ""))
    total = int(payload.get("total", 0))
    pending = int(payload.get("pending", 0))
    classified = int(payload.get("classified", 0))
    review = payload.get("review")
    lotes_llm_falhos = payload.get("lotes_llm_falhos")

    counters: dict[str, int | None] = {
        "transactions_total": total,
        "transactions_classified": classified,
        "transactions_pending": pending,
    }
    if isinstance(review, int):
        counters["transactions_review"] = review
    if isinstance(lotes_llm_falhos, int):
        counters["llm_batches_failed"] = lotes_llm_falhos
    job_store.update_counters(job_id, **counters)

    if phase == "loaded":
        detail = f"Carregadas {total} transações para classificar"
    elif phase == "rules_applied":
        por_regra = int(payload.get("por_regra", 0))
        detail = f"Regras concluídas · {por_regra} classificadas · {pending} pendentes"
    elif phase == "llm_running":
        llm_processed = int(payload.get("llm_processed", 0))
        llm_total = int(payload.get("llm_total", 0))
        detail = f"LLM {llm_processed}/{llm_total} · {classified} classificadas · {pending} pendentes"
    elif phase == "finished":
        review_count = int(payload.get("review", 0))
        detail = f"Classificação concluída · {classified} classificadas · {pending} pendentes · {review_count} revisão"
    else:
        detail = f"{classified} classificadas · {pending} pendentes"

    _update_step_detail(job_id, "classify", detail)


def run_analyze(job_id: str, mes: str) -> dict:
    """
    Etapa 3: Calcula métricas, detecta anomalias, grava metrics_{mes}.json e report_{mes}.md.
    Retorna: { "anomalias":2, "report_path": "..." }
    """
    from backend.analyzer.anomaly import detect_anomalies
    from backend.analyzer.metrics import compute_month, save_metrics_json
    from backend.analyzer.report import write_month_report

    _step_start(job_id, "analyze")
    try:
        metrics = compute_month(mes, project_root=ROOT)
        month_dir = PROCESSED_ROOT / mes
        save_metrics_json(month_dir, metrics)

        anomalies = detect_anomalies(mes, metrics, project_root=ROOT)
        report_path = write_month_report(ROOT, metrics, anomalies)

        detail = f"Métricas geradas · {len(anomalies)} anomalia(s) detectada(s)"
        _step_done(job_id, "analyze", detail)
        return {"anomalias": len(anomalies), "report_path": str(report_path)}

    except Exception as exc:
        _step_error(job_id, "analyze", str(exc))
        raise


EXTRACT_ONLY_STEPS = [
    ("parse", "Extraindo transações dos PDFs"),
]

PIPELINE_STEPS = [
    ("parse", "Extraindo transações dos PDFs"),
    ("classify", "Classificando transações"),
    ("analyze", "Calculando métricas e anomalias"),
]

CLASSIFY_STEPS = [
    ("classify", "Classificando transações"),
    ("analyze", "Calculando métricas e anomalias"),
]


def run_extract_pipeline(job_id: str, *, use_fallback: bool = False) -> None:
    """Somente parse. Usado quando o usuário quer desacoplar extração da classificação."""
    job_store.set_job_status(job_id, "running")
    try:
        result = run_parse(job_id, use_fallback=use_fallback)
        mes = result["mes"]
        if mes:
            job_store.update_job(job_id, mes=mes)
        job_store.set_job_status(job_id, "done")
    except Exception as exc:
        job_store.set_job_status(job_id, "error", error=str(exc))
        logger.error("Pipeline extract falhou no job %s: %s", job_id, exc, exc_info=True)


def run_full_pipeline(job_id: str, *, use_llm: bool = True, use_fallback: bool = False) -> None:
    """Parse + classify + analyze. Usado pelo upload flow."""
    job_store.set_job_status(job_id, "running")
    try:
        result = run_parse(job_id, use_fallback=use_fallback)
        mes = result["mes"]
        if not mes:
            raise RuntimeError("Nenhum mês detectado nos PDFs processados.")

        job_store.update_job(job_id, mes=mes)

        run_classify(job_id, mes, use_llm=use_llm)
        run_analyze(job_id, mes)

        job_store.set_job_status(job_id, "done")

    except Exception as exc:
        job_store.set_job_status(job_id, "error", error=str(exc))
        logger.error("Pipeline falhou no job %s: %s", job_id, exc, exc_info=True)


def run_classify_pipeline(job_id: str, mes: str, *, use_llm: bool = True) -> None:
    """Classify + analyze para um mês já parseado. Usado pelo botão 'Rodar Pipeline'."""
    job_store.set_job_status(job_id, "running")
    try:
        run_classify(job_id, mes, use_llm=use_llm)
        run_analyze(job_id, mes)
        job_store.set_job_status(job_id, "done")
    except Exception as exc:
        job_store.set_job_status(job_id, "error", error=str(exc))
        logger.error("Pipeline classify falhou no job %s: %s", job_id, exc, exc_info=True)
