from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from analyzer.anomaly import detect_anomalies
from analyzer.metrics import compute_month
from analyzer.report import write_month_report
from models.transaction import Classificacao, Transaction


def _processed_root(project: Path) -> Path:
    root = project / "data" / "processed"
    root.mkdir(parents=True)
    return root


def _write_month(
    processed: Path,
    month_key: str,
    transactions: list[Transaction],
) -> None:
    month_dir = processed / month_key
    month_dir.mkdir(parents=True)
    (month_dir / "fatura.json").write_text(
        json.dumps([transaction.model_dump(mode="json") for transaction in transactions], ensure_ascii=False),
        encoding="utf-8",
    )


def test_compute_month_overview_and_card(tmp_path: Path) -> None:
    processed = _processed_root(tmp_path)
    transactions = [
        Transaction(
            id="1",
            data=date(2026, 3, 5),
            descricao_original="LOJA A",
            valor=100.0,
            tipo="debito",
            meio="cartao_credito",
            fonte="fatura",
            classificacao=Classificacao(
                categoria="Alimentação",
                natureza="Essencial",
                compromisso="a_vista",
                contexto="Rotina Campinas",
                metodo="regra",
                confianca=1.0,
            ),
        ),
        Transaction(
            id="2",
            data=date(2026, 2, 1),
            descricao_original="LOJA B PARCELA",
            valor=50.0,
            tipo="debito",
            meio="cartao_credito",
            fonte="fatura",
            classificacao=Classificacao(
                categoria="Lazer",
                natureza="Lazer",
                compromisso="parcela",
                contexto="Rotina Campinas",
                metodo="regra",
                confianca=1.0,
            ),
        ),
        Transaction(
            id="3",
            data=date(2026, 3, 20),
            descricao_original="SALARIO",
            valor=3000.0,
            tipo="credito",
            meio="debito_pix",
            fonte="extrato",
            classificacao=Classificacao(
                categoria="Receita",
                natureza="Essencial",
                metodo="regra",
                confianca=1.0,
            ),
        ),
    ]
    _write_month(processed, "2026-03", transactions)
    metrics = compute_month("2026-03", project_root=tmp_path)
    assert metrics.visao_geral.total_gastos == 150.0
    assert metrics.visao_geral.total_receitas == 3000.0
    assert metrics.composicao_fatura_cartao.total_base == 150.0
    grupos = {g.chave: g.valor for g in metrics.composicao_fatura_cartao.grupos}
    assert grupos.get("parcela_anterior", 0) == 50.0
    assert grupos.get("gasto_novo", 0) == 100.0


def test_anomaly_pendente_threshold(tmp_path: Path) -> None:
    processed = _processed_root(tmp_path)
    transactions = [
        Transaction(
            id=str(index),
            data=date(2026, 3, 1),
            descricao_original=f"T{index}",
            valor=10.0,
            tipo="debito",
            meio="debito_pix",
            fonte="extrato",
            classificacao=Classificacao(metodo="pendente" if index < 2 else "regra", confianca=0.0),
        )
        for index in range(5)
    ]
    _write_month(processed, "2026-03", transactions)
    metrics = compute_month("2026-03", project_root=tmp_path)
    anomalies = detect_anomalies("2026-03", metrics, project_root=tmp_path)
    tipos = {anomaly.tipo for anomaly in anomalies}
    assert "pendentes_classificacao" in tipos


def test_write_report_creates_files(tmp_path: Path) -> None:
    processed = _processed_root(tmp_path)
    _write_month(
        processed,
        "2026-03",
        [
            Transaction(
                id="1",
                data=date(2026, 3, 1),
                descricao_original="X",
                valor=10.0,
                tipo="debito",
                meio="cartao_credito",
                fonte="fatura",
                classificacao=Classificacao(
                    categoria="Outros",
                    metodo="regra",
                    confianca=1.0,
                    contexto="Outros",
                    natureza="Lazer",
                ),
            )
        ],
    )
    metrics = compute_month("2026-03", project_root=tmp_path)
    path = write_month_report(tmp_path, metrics, [])
    assert path.exists()
    assert (processed / "2026-03" / "metrics_2026-03.json").exists()
