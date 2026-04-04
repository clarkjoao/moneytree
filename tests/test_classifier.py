from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

import pytest

from backend.classifier.context_engine import apply_context_engine
from backend.classifier.llm_classifier import _parse_llm_payload
from backend.classifier.recurrence_detector import run_recurrence_detection
from backend.classifier.review import apply_review_csv, needs_human_review, write_review_csv
from backend.classifier.rule_engine import apply_rule_engine, append_exact_rule
from backend.models.transaction import Classificacao, Transaction


def test_por_descricao_substring_rule() -> None:
    transaction = Transaction(
        data=date(2026, 1, 1),
        descricao_original="PG *UBER TRIP HELP",
        valor=22.0,
        tipo="debito",
        meio="cartao_credito",
        fonte="fatura",
        classificacao=Classificacao(metodo="pendente", confianca=0.0),
    )
    regras = {
        "por_descricao": {"~UBER": {"categoria": "Transporte", "natureza": "Lazer"}},
        "padroes_descricao": [],
        "mapeamentos": [],
    }
    perfil: dict = {"contas_proprias": [], "pessoas_conhecidas": {}}
    apply_rule_engine([transaction], regras, perfil)
    assert transaction.classificacao.categoria == "Transporte"
    assert transaction.classificacao.metodo == "regra"


def test_por_descricao_exact_rule() -> None:
    transaction = Transaction(
        data=date(2026, 1, 2),
        descricao_original="LOJA EXATA",
        valor=5.0,
        tipo="debito",
        meio="debito_pix",
        fonte="extrato",
        classificacao=Classificacao(metodo="pendente", confianca=0.0),
    )
    regras = {
        "por_descricao": {"LOJA EXATA": {"categoria": "Alimentação"}},
        "padroes_descricao": [],
        "mapeamentos": [],
    }
    perfil = {"contas_proprias": [], "pessoas_conhecidas": {}}
    apply_rule_engine([transaction], regras, perfil)
    assert transaction.classificacao.metodo == "regra"
    assert transaction.classificacao.categoria == "Alimentação"


def test_conta_propria_rule(tmp_path: Path) -> None:
    transaction = Transaction(
        data=date(2026, 1, 3),
        descricao_original="PIX para exemplo.pix.usuario@email.com",
        valor=100.0,
        tipo="debito",
        meio="debito_pix",
        fonte="extrato",
        classificacao=Classificacao(metodo="pendente", confianca=0.0),
    )
    regras: dict = {"por_descricao": {}, "padroes_descricao": [], "mapeamentos": []}
    perfil = {
        "contas_proprias": ["exemplo.pix.usuario@email.com"],
        "pessoas_conhecidas": {},
    }
    apply_rule_engine([transaction], regras, perfil)
    assert transaction.classificacao.categoria == "Transferência Interna"


def test_context_city_suffix() -> None:
    transaction = Transaction(
        data=date(2026, 1, 4),
        descricao_original="RESTAURANTE XYZ.SAO PAULO",
        valor=80.0,
        tipo="debito",
        meio="cartao_credito",
        fonte="fatura",
        classificacao=Classificacao(metodo="regra", confianca=1.0, contexto=None),
    )
    perfil = {
        "cidades_contexto": {"SAO PAULO": "Trabalho SP"},
        "estabelecimentos_ancora": [],
        "viagens": [],
        "contexto_padrao": "Outros",
    }
    apply_context_engine([transaction], perfil)
    assert transaction.classificacao.contexto == "Trabalho SP"


def test_parse_llm_payload_array() -> None:
    raw = 'Prefix [{"id":"a1","categoria":"X","natureza":null,"recorrencia":null,"compromisso":null,"contexto":null,"confianca":0.5}] suffix'
    parsed = _parse_llm_payload(raw)
    assert len(parsed) == 1
    assert parsed[0]["id"] == "a1"


def test_needs_human_review() -> None:
    pending = Transaction(
        data=date(2026, 1, 1),
        descricao_original="A",
        valor=1.0,
        tipo="debito",
        meio="cartao_credito",
        fonte="f",
        classificacao=Classificacao(metodo="pendente", confianca=0.0),
    )
    low = Transaction(
        data=date(2026, 1, 1),
        descricao_original="B",
        valor=1.0,
        tipo="debito",
        meio="cartao_credito",
        fonte="f",
        classificacao=Classificacao(metodo="llm", confianca=0.5, categoria="Outros"),
    )
    assert needs_human_review(pending) is True
    assert needs_human_review(low) is True


def test_review_csv_and_apply(tmp_path: Path) -> None:
    processed = tmp_path / "processed" / "2026-03"
    processed.mkdir(parents=True)
    transaction = Transaction(
        id="tid-1",
        data=date(2026, 3, 10),
        descricao_original="LOJA REVIEW",
        valor=15.0,
        tipo="debito",
        meio="cartao_credito",
        fonte="fatura",
        classificacao=Classificacao(
            metodo="llm",
            confianca=0.5,
            categoria="Outros",
            natureza="Lazer",
            contexto="Outros",
        ),
    )
    fatura_path = processed / "fatura.json"
    fatura_path.write_text(
        json.dumps([transaction.model_dump(mode="json")], ensure_ascii=False),
        encoding="utf-8",
    )
    csv_path = write_review_csv(processed, [transaction])
    assert csv_path.exists()
    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    rows[0]["sugestao_categoria"] = "Alimentação"
    rows[0]["confirmado"] = "sim"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerow(rows[0])

    regras_path = tmp_path / "regras.json"
    regras_path.write_text(
        json.dumps({"por_descricao": {}, "padroes_descricao": [], "mapeamentos": []}),
        encoding="utf-8",
    )
    apply_review_csv(processed, "2026-03", csv_path, regras_path, tmp_path / "processed")
    data = json.loads((processed / "classificacao_2026-03.json").read_text(encoding="utf-8"))
    saved = data["by_id"]["tid-1"]
    assert saved["categoria"] == "Alimentação"
    assert saved["metodo"] == "confirmado"
    learned = json.loads(regras_path.read_text(encoding="utf-8"))
    assert "LOJA REVIEW" in learned["por_descricao"]


def test_append_exact_rule_writes_file(tmp_path: Path) -> None:
    path = tmp_path / "regras.json"
    classification = Classificacao(
        categoria="X",
        natureza="Essencial",
        metodo="confirmado",
        confianca=1.0,
    )
    append_exact_rule(path, "DESC EXATA", classification)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["por_descricao"]["DESC EXATA"]["categoria"] == "X"


def test_recurrence_duckdb_two_months(tmp_path: Path) -> None:
    root = tmp_path / "processed"
    (root / "2026-01").mkdir(parents=True)
    (root / "2026-02").mkdir(parents=True)
    common = {
        "descricao_original": "ASSINATURA STREAM",
        "valor": 50.0,
        "tipo": "debito",
        "meio": "cartao_credito",
        "fonte": "f",
        "cartao_final": None,
        "parcela_info": None,
        "metadados": None,
        "classificacao": {"metodo": "pendente", "confianca": 0.0},
    }
    row_a = {"id": "a", "data": "2026-01-15", **common}
    row_b = {"id": "b", "data": "2026-02-10", **common}
    (root / "2026-01" / "fatura.json").write_text(json.dumps([row_a]), encoding="utf-8")
    (root / "2026-02" / "fatura.json").write_text(json.dumps([row_b]), encoding="utf-8")

    current_tx = Transaction(
        id="c",
        data=date(2026, 3, 5),
        descricao_original="ASSINATURA STREAM",
        valor=50.0,
        tipo="debito",
        meio="cartao_credito",
        fonte="fatura",
        classificacao=Classificacao(metodo="pendente", confianca=0.0),
    )
    out = run_recurrence_detection(root, "2026-03", [current_tx])
    assert out is not None
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert len(payload["items"]) >= 1
