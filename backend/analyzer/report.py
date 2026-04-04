from __future__ import annotations

from datetime import datetime
from pathlib import Path

from backend.analyzer.anomaly import Anomaly
from backend.analyzer.metrics import MonthMetrics, save_metrics_json


_MESES_PT = {
    "01": "Janeiro",
    "02": "Fevereiro",
    "03": "Março",
    "04": "Abril",
    "05": "Maio",
    "06": "Junho",
    "07": "Julho",
    "08": "Agosto",
    "09": "Setembro",
    "10": "Outubro",
    "11": "Novembro",
    "12": "Dezembro",
}


def _titulo_mes(mes: str) -> str:
    year, month = mes.split("-", 1)
    nome = _MESES_PT.get(month, month)
    return f"{nome} {year}"


def _tabela_markdown(headers: list[str], linhas: list[list[str]]) -> str:
    linhas_txt = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for linha in linhas:
        linhas_txt.append("| " + " | ".join(linha) + " |")
    return "\n".join(linhas_txt)


def build_report_markdown(metrics: MonthMetrics, anomalies: list[Anomaly]) -> str:
    titulo = _titulo_mes(metrics.mes)
    linhas: list[str] = [
        f"# MoneyTree — Relatório {titulo}",
        "",
        "## Resumo",
        "",
        _tabela_markdown(
            ["Métrica", "Valor"],
            [
                ["Total de gastos (R$)", f"{metrics.visao_geral.total_gastos:,.2f}"],
                ["Total de receitas (R$)", f"{metrics.visao_geral.total_receitas:,.2f}"],
                ["Saldo líquido (R$)", f"{metrics.visao_geral.saldo_liquido:,.2f}"],
                [
                    "% gasto / receita",
                    (
                        f"{metrics.visao_geral.percentual_gasto_sobre_receita:.2f}%"
                        if metrics.visao_geral.percentual_gasto_sobre_receita is not None
                        else "—"
                    ),
                ],
            ],
        ),
        "",
        "## Composição da Fatura (cartão)",
        "",
        _tabela_markdown(
            ["Grupo", "Valor (R$)", "% da fatura"],
            [
                [grupo.rotulo, f"{grupo.valor:,.2f}", f"{grupo.percentual:.2f}%"]
                for grupo in metrics.composicao_fatura_cartao.grupos
            ]
            + [
                [
                    "**Total**",
                    f"{metrics.composicao_fatura_cartao.total_base:,.2f}",
                    "100%" if metrics.composicao_fatura_cartao.total_base > 0 else "0%",
                ]
            ],
        ),
        "",
        "## Gastos por Categoria",
        "",
        _tabela_markdown(
            ["Categoria", "Total (R$)", "%", "Qtd. transações"],
            [
                [
                    row.categoria,
                    f"{row.total:,.2f}",
                    f"{row.percentual:.2f}%",
                    str(row.quantidade_transacoes),
                ]
                for row in metrics.gastos_por_categoria
            ],
        ),
        "",
        "## Gastos por Contexto",
        "",
    ]

    for block in metrics.gastos_por_contexto:
        linhas.append(f"### {block.contexto} — **R$ {block.total:,.2f}**")
        linhas.append("")
        if block.top_estabelecimentos:
            linhas.append(
                _tabela_markdown(
                    ["Estabelecimento", "Valor (R$)"],
                    [[merchant.descricao_exibicao, f"{merchant.valor:,.2f}"] for merchant in block.top_estabelecimentos],
                )
            )
        else:
            linhas.append("_Sem detalhamento._")
        linhas.append("")

    linhas.extend(
        [
            "## Natureza dos Gastos",
            "",
            _tabela_markdown(
                ["Natureza", "Total (R$)", "%"],
                [[row.natureza, f"{row.total:,.2f}", f"{row.percentual:.2f}%"] for row in metrics.gastos_por_natureza],
            ),
            "",
            "## Recorrências",
            "",
        ]
    )

    if metrics.recorrencias:
        linhas.append(
            _tabela_markdown(
                ["Descrição", "Valor mês (R$)", "Δ% vs média 3m"],
                [
                    [
                        row.descricao_exibicao,
                        f"{row.valor_mes:,.2f}",
                        (
                            f"{row.variacao_percentual_vs_media_3m:+.2f}%"
                            if row.variacao_percentual_vs_media_3m is not None
                            else "—"
                        ),
                    ]
                    for row in metrics.recorrencias
                ],
            )
        )
    else:
        linhas.append("_Nenhuma transação Fixa / Variável recorrente no período._")

    linhas.append("")

    if metrics.comparativo_categorias:
        linhas.extend(
            [
                "## Comparativo com Meses Anteriores",
                "",
                _tabela_markdown(
                    ["Categoria", "Mês atual (R$)", "Média 3 meses (R$)", "Variação %"],
                    [
                        [
                            row.categoria,
                            f"{row.valor_mes_atual:,.2f}",
                            f"{row.media_tres_meses_anteriores:,.2f}",
                            f"{row.variacao_percentual:+.2f}%",
                        ]
                        for row in metrics.comparativo_categorias
                    ],
                ),
                "",
            ]
        )
        linhas.append("**Destaques (|variação| > 20%):**")
        linhas.append("")
        destaques = [row for row in metrics.comparativo_categorias if abs(row.variacao_percentual) > 20]
        if destaques:
            for row in destaques:
                linhas.append(
                    f"- **{row.categoria}**: {row.variacao_percentual:+.2f}% "
                    f"(atual R$ {row.valor_mes_atual:,.2f} vs média R$ {row.media_tres_meses_anteriores:,.2f})"
                )
        else:
            linhas.append("_Nenhuma categoria com variação acima de 20%._")
        linhas.append("")

    linhas.extend(["## ⚠️ Anomalias Detectadas", ""])
    if anomalies:
        for item in anomalies:
            ref = f" _({item.referencia})_" if item.referencia else ""
            valor_txt = f" — valor: {item.valor:,.2f}" if item.valor is not None else ""
            linhas.append(f"- **{item.tipo}**{valor_txt}: {item.descricao}{ref}")
    else:
        linhas.append("Nenhuma anomalia detectada.")

    linhas.extend(
        [
            "",
            "---",
            f"_Gerado em {datetime.now().strftime('%Y-%m-%d %H:%M')} | "
            f"Transações: {metrics.total_transacoes} | "
            f"Pendentes: {metrics.transacoes_pendentes}_",
        ]
    )

    return "\n".join(linhas)


def write_month_report(
    project_root: Path,
    metrics: MonthMetrics,
    anomalies: list[Anomaly],
) -> Path:
    month_dir = project_root / "data" / "processed" / metrics.mes
    month_dir.mkdir(parents=True, exist_ok=True)
    save_metrics_json(month_dir, metrics)
    path = month_dir / f"report_{metrics.mes}.md"
    path.write_text(build_report_markdown(metrics, anomalies), encoding="utf-8")
    return path


def print_metrics_tabular(metrics: MonthMetrics) -> None:
    overview = metrics.visao_geral
    print(f"Mês: {metrics.mes}")
    print(f"{'Métrica':<30} {'Valor':>15}")
    print("-" * 46)
    print(f"{'Total gastos':<30} {overview.total_gastos:>15,.2f}")
    print(f"{'Total receitas':<30} {overview.total_receitas:>15,.2f}")
    print(f"{'Saldo líquido':<30} {overview.saldo_liquido:>15,.2f}")
    pct = overview.percentual_gasto_sobre_receita
    print(f"{'% gasto/receita':<30} {str(pct) + '%' if pct is not None else '—':>15}")
    print(f"{'Transações':<30} {metrics.total_transacoes:>15}")
    print(f"{'Pendentes':<30} {metrics.transacoes_pendentes:>15}")
    print()
    print("Composição fatura (cartão)")
    print(f"{'Grupo':<40} {'R$':>12} {'%':>8}")
    for grupo in metrics.composicao_fatura_cartao.grupos:
        print(f"{grupo.rotulo:<40} {grupo.valor:>12,.2f} {grupo.percentual:>7.1f}%")
    print(f"{'TOTAL':<40} {metrics.composicao_fatura_cartao.total_base:>12,.2f}")
    print()
    print("Top categorias")
    for row in metrics.gastos_por_categoria[:15]:
        print(f"  {row.categoria:<28} {row.total:>10,.2f}  ({row.quantidade_transacoes} tx)")
