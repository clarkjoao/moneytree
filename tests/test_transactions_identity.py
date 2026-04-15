from __future__ import annotations

from datetime import date

from backend.models.transaction import Classificacao, ParcelaInfo, Transaction, dedupe_transactions


def test_transaction_id_is_stable_for_same_payload() -> None:
    first = Transaction(
        data=date(2026, 4, 10),
        descricao_original="PADARIA CENTRAL",
        valor=35.9,
        tipo="debito",
        meio="cartao_credito",
        fonte="fatura_mastercard_2026-04",
        cartao_final="1354",
        classificacao=Classificacao(metodo="pendente", confianca=0.0),
    )
    second = Transaction(
        data=date(2026, 4, 10),
        descricao_original="PADARIA CENTRAL",
        valor=35.9,
        tipo="debito",
        meio="cartao_credito",
        fonte="fatura_mastercard_2026-04",
        cartao_final="1354",
        classificacao=Classificacao(metodo="pendente", confianca=0.0),
    )

    assert first.id == second.id


def test_parcelas_share_same_compra_id_but_keep_distinct_transaction_ids() -> None:
    parcela_1 = Transaction(
        data=date(2026, 2, 23),
        descricao_original="VagnerPereira 01/04",
        valor=587.5,
        tipo="debito",
        meio="cartao_credito",
        fonte="fatura_mastercard_2026-03",
        cartao_final="1354",
        parcela_info=ParcelaInfo(numero=1, total=4),
    )
    parcela_2 = Transaction(
        data=date(2026, 2, 23),
        descricao_original="VagnerPereira 02/04",
        valor=587.5,
        tipo="debito",
        meio="cartao_credito",
        fonte="fatura_mastercard_2026-04",
        cartao_final="1354",
        parcela_info=ParcelaInfo(numero=2, total=4),
    )

    assert parcela_1.id != parcela_2.id
    assert parcela_1.compra_id is not None
    assert parcela_1.compra_id == parcela_2.compra_id


def test_dedupe_transactions_removes_duplicate_upload_rows() -> None:
    original = Transaction(
        data=date(2026, 4, 10),
        descricao_original="PADARIA CENTRAL",
        valor=35.9,
        tipo="debito",
        meio="cartao_credito",
        fonte="fatura_mastercard_2026-04",
        cartao_final="1354",
    )
    duplicate = Transaction(
        data=date(2026, 4, 10),
        descricao_original="PADARIA CENTRAL",
        valor=35.9,
        tipo="debito",
        meio="cartao_credito",
        fonte="fatura_mastercard_2026-04",
        cartao_final="1354",
    )

    deduped = dedupe_transactions([original, duplicate])

    assert len(deduped) == 1
    assert deduped[0].id == original.id
