from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backend.analyzer.flat import is_fatura_payment_line
from backend.analyzer.metrics import MonthMetrics, _days_in_month, _is_month_dir
from backend.transaction_store import load_month_transactions


@dataclass
class Anomaly:
    tipo: str
    descricao: str
    valor: float | None
    referencia: str | None


def _eligible_gasto(transaction) -> bool:
    if transaction.tipo != "debito":
        return False
    classification = transaction.classificacao
    if classification.categoria in ("Transferência Interna", "Receita"):
        return False
    if is_fatura_payment_line(transaction.descricao_original):
        return False
    return True


def _parcela_primeira_parcela_index(processed_root: Path) -> set[tuple[str, int]]:
    """Pares (descrição normalizada, total_parcelas) com parcela 1/N presente em algum mês."""
    keys: set[tuple[str, int]] = set()
    if not processed_root.is_dir():
        return keys
    for month_dir in sorted(processed_root.iterdir()):
        if not month_dir.is_dir() or not _is_month_dir(month_dir.name):
            continue
        for transaction in load_month_transactions(processed_root, month_dir.name):
            parcela = transaction.parcela_info
            if parcela is None or parcela.numero != 1:
                continue
            keys.add((transaction.descricao_original.strip().upper(), parcela.total))
    return keys


def detect_anomalies(
    mes: str,
    metrics: MonthMetrics,
    *,
    project_root: Path,
) -> list[Anomaly]:
    processed_root = project_root / "data" / "processed"
    transactions = load_month_transactions(processed_root, mes)
    found: list[Anomaly] = []

    days = max(_days_in_month(mes), 1)
    media_diaria = metrics.visao_geral.total_gastos / days if metrics.visao_geral.total_gastos > 0 else 0.0
    limite_alto = 0.30 * media_diaria if media_diaria > 0 else None

    if limite_alto and limite_alto > 0:
        for transaction in transactions:
            if not _eligible_gasto(transaction):
                continue
            if float(transaction.valor) > limite_alto:
                found.append(
                    Anomaly(
                        tipo="gasto_pontual_alto",
                        descricao=(
                            f"Transação '{transaction.descricao_original[:60]}' "
                            f"({transaction.valor:.2f}) > 30% da média diária ({media_diaria:.2f}/dia)"
                        ),
                        valor=float(transaction.valor),
                        referencia=f"limite_30pct_diario={limite_alto:.2f}",
                    )
                )

    total_tx = metrics.total_transacoes
    if total_tx > 0 and metrics.transacoes_pendentes / total_tx > 0.10:
        found.append(
            Anomaly(
                tipo="pendentes_classificacao",
                descricao=(
                    f"{metrics.transacoes_pendentes} de {total_tx} transações ainda pendentes "
                    f"({100.0 * metrics.transacoes_pendentes / total_tx:.1f}%)"
                ),
                valor=float(metrics.transacoes_pendentes),
                referencia="limite=10%",
            )
        )

    for row in metrics.comparativo_categorias:
        if row.media_tres_meses_anteriores <= 0:
            continue
        limite = 1.5 * row.media_tres_meses_anteriores
        if row.valor_mes_atual > limite:
            found.append(
                Anomaly(
                    tipo="categoria_fora_do_padrao",
                    descricao=(
                        f"Categoria '{row.categoria}' no mês ({row.valor_mes_atual:.2f}) "
                        f"> 50% acima da média dos 3 meses ({row.media_tres_meses_anteriores:.2f})"
                    ),
                    valor=row.valor_mes_atual,
                    referencia=f"media_3m={row.media_tres_meses_anteriores:.2f}",
                )
            )

    parcela_parents = _parcela_primeira_parcela_index(processed_root)
    for transaction in transactions:
        parcela = transaction.parcela_info
        if parcela is None or parcela.numero <= 1:
            continue
        key = (transaction.descricao_original.strip().upper(), parcela.total)
        if key not in parcela_parents:
            found.append(
                Anomaly(
                    tipo="parcela_nao_mapeada",
                    descricao=(
                        f"Parcela {parcela.numero}/{parcela.total} sem compra 1/{parcela.total} "
                        f"encontrada para '{transaction.descricao_original[:50]}'"
                    ),
                    valor=float(transaction.valor),
                    referencia=None,
                )
            )

    return found
