from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.models.transaction import Classificacao, Transaction
from backend.parsers.banks.itau.extrato import extrato_metadata_kind, try_parse_extrato_line
from backend.parsers.banks.itau.fatura import ItauFaturaParser, parse_fatura_line_for_tests
from backend.classifier.rule_engine import apply_rule_engine


def test_fatura_parse_basic_line() -> None:
    line = "15/03/2026 MERCADO EXEMPLO  150,75"
    transaction = parse_fatura_line_for_tests(
        line,
        default_year=2026,
        fonte="fatura_mastercard_2026-03",
        cartao_final="1354",
    )
    assert transaction is not None
    assert transaction.data == date(2026, 3, 15)
    assert transaction.valor == pytest.approx(150.75)
    assert transaction.tipo == "debito"
    assert transaction.meio == "cartao_credito"
    assert transaction.cartao_final == "1354"
    assert transaction.parcela_info is None
    assert transaction.classificacao.compromisso == "a_vista"


def test_fatura_parcela_info() -> None:
    line = "10/02/2026 LOJA ABC 03/12  200,00"
    transaction = parse_fatura_line_for_tests(
        line,
        default_year=2026,
        fonte="fatura_mastercard_2026-02",
        cartao_final="2219",
    )
    assert transaction is not None
    assert transaction.parcela_info is not None
    assert transaction.parcela_info.numero == 3
    assert transaction.parcela_info.total == 12
    assert transaction.classificacao.compromisso == "parcela"


def test_fatura_skip_pagamento_efetuado() -> None:
    line = "PAGAMENTO EFETUADO EM 01/02/2026"
    assert (
        parse_fatura_line_for_tests(
            line,
            default_year=2026,
            fonte="fatura",
            cartao_final=None,
        )
        is None
    )


def test_fatura_skip_zero_amount() -> None:
    line = "12/03/2026 AJUSTE OU RESUMO  0,00"
    assert (
        parse_fatura_line_for_tests(
            line,
            default_year=2026,
            fonte="fatura",
            cartao_final=None,
        )
        is None
    )


def test_fatura_credito_desc() -> None:
    line = "05/01/2026 DESC ANTECIPA PARCELAS  -80,00"
    transaction = parse_fatura_line_for_tests(
        line,
        default_year=2026,
        fonte="fatura",
        cartao_final=None,
    )
    assert transaction is not None
    assert transaction.tipo == "credito"
    assert transaction.valor == pytest.approx(80.0)


def test_fatura_international_metadados() -> None:
    line = "02/04/2026 HOTEL USD 100,00 (R$ 550,25)  550,25"
    transaction = parse_fatura_line_for_tests(
        line,
        default_year=2026,
        fonte="fatura",
        cartao_final=None,
    )
    assert transaction is not None
    assert transaction.metadados is not None
    assert transaction.metadados.get("moeda_original") == "USD"


def test_extrato_credito_debito() -> None:
    credito, meta = try_parse_extrato_line(
        "05/03/2026 PIX RECEBIDO  1.500,00",
        fonte="extrato_2026-03",
        default_year=2026,
    )
    assert meta is None
    assert credito is not None
    assert credito.tipo == "credito"
    debito, meta2 = try_parse_extrato_line(
        "06/03/2026 BOLETO CONTA  -320,50",
        fonte="extrato_2026-03",
        default_year=2026,
    )
    assert meta2 is None
    assert debito is not None
    assert debito.tipo == "debito"
    assert debito.valor == pytest.approx(320.5)


def test_extrato_metadata_filters() -> None:
    assert extrato_metadata_kind("ITAU BLACK FATURA") == "pagamento_fatura"
    assert extrato_metadata_kind("FATURA PAGA PERSON MULTI") == "pagamento_fatura"
    assert extrato_metadata_kind("SALDO DO DIA") == "saldo"
    assert extrato_metadata_kind("REND PAGO APLIC AUT MAIS") == "rendimento_aplicacao"

    transaction, kind = try_parse_extrato_line(
        "01/03/2026 ITAU BLACK CARTAO  -5.000,00",
        fonte="extrato_2026-03",
        default_year=2026,
    )
    assert transaction is None
    assert kind == "pagamento_fatura"


def test_extrato_rendimento_jsonl(tmp_path: Path) -> None:
    line = "02/03/2026 REND PAGO APLIC AUT MAIS  12,34"
    transaction, kind = try_parse_extrato_line(
        line,
        fonte="extrato_2026-03",
        default_year=2026,
        month_dir=tmp_path,
    )
    assert transaction is None
    assert kind == "rendimento_aplicacao"
    jsonl = tmp_path / "extrato_metadados.jsonl"
    assert jsonl.exists()
    payload = json.loads(jsonl.read_text(encoding="utf-8").strip())
    assert payload["tipo"] == "rendimento_aplicacao"
    assert payload["valor"] == pytest.approx(12.34)


def test_apply_rule_engine_merges_compromisso() -> None:
    transaction = Transaction(
        data=date(2026, 3, 1),
        descricao_original="COMPRA NA LOJA XYZ",
        valor=10.0,
        tipo="debito",
        meio="cartao_credito",
        fonte="fatura",
        parcela_info=None,
        classificacao=Classificacao(
            compromisso="parcela",
            metodo="pendente",
            confianca=0.0,
        ),
    )
    regras = {
        "por_descricao": {},
        "mapeamentos": [],
        "padroes_descricao": [{"contem": "LOJA XYZ", "categoria": "Alimentação"}],
    }
    perfil: dict = {"contas_proprias": [], "pessoas_conhecidas": {}}
    apply_rule_engine([transaction], regras, perfil)
    assert transaction.classificacao.metodo == "regra"
    assert transaction.classificacao.categoria == "Alimentação"
    assert transaction.classificacao.compromisso == "parcela"


def test_fallback_triggers_record_unparsed(tmp_path: Path) -> None:
    fake_page = MagicMock()
    fake_page.extract_text.return_value = "x" * 250
    fake_page.extract_tables.return_value = [[["a", "b"]]]

    fake_pdf = MagicMock()
    fake_pdf.pages = [fake_page]

    parser = ItauFaturaParser(fonte="fatura_test", default_year=2026)
    pdf_path = Path("dummy_fatura.pdf")

    with patch("backend.parsers.banks.itau.fatura.pdfplumber.open") as open_mock, patch(
        "backend.parsers.banks.itau.fatura.record_unparsed_page"
    ) as record_mock:
        open_mock.return_value.__enter__.return_value = fake_pdf
        open_mock.return_value.__exit__.return_value = None
        parser.parse_with_options(
            pdf_path,
            month_dir=tmp_path,
            use_fallback=True,
        )
        record_mock.assert_called_once()
