from __future__ import annotations

import calendar
import json
import os
import re
import tempfile
from pathlib import Path

import duckdb
from pydantic import BaseModel, Field

from backend.analyzer.flat import flatten_for_analysis
from backend.transaction_store import load_month_transactions


def _project_root_default() -> Path:
    return Path(__file__).resolve().parents[1]


def _is_month_dir(name: str) -> bool:
    return bool(re.match(r"^\d{4}-\d{2}$", name))


def _months_with_data(processed_root: Path) -> list[str]:
    found: list[str] = []
    if not processed_root.is_dir():
        return found
    for path in sorted(processed_root.iterdir()):
        if not path.is_dir() or not _is_month_dir(path.name):
            continue
        if (path / "fatura.json").exists() or (path / "extrato.json").exists():
            found.append(path.name)
    return found


def _prior_month_keys(processed_root: Path, mes: str, limit: int = 3) -> list[str]:
    return [key for key in _months_with_data(processed_root) if key < mes][-limit:]


def _days_in_month(mes: str) -> int:
    year_s, month_s = mes.split("-")
    return calendar.monthrange(int(year_s), int(month_s))[1]


def _assert_month_key(mes: str) -> None:
    if not _is_month_dir(mes):
        raise ValueError(f"Mês inválido (use YYYY-MM): {mes}")


def _year_month_int_from_mes(mes: str) -> int:
    year_s, month_s = mes.split("-", 1)
    return int(year_s) * 100 + int(month_s)


class OverviewMetrics(BaseModel):
    total_gastos: float
    total_receitas: float
    saldo_liquido: float
    percentual_gasto_sobre_receita: float | None


class CardCompositionGroup(BaseModel):
    chave: str
    rotulo: str
    valor: float
    percentual: float


class CardCompositionMetrics(BaseModel):
    grupos: list[CardCompositionGroup]
    total_base: float


class CategorySpendRow(BaseModel):
    categoria: str
    total: float
    percentual: float
    quantidade_transacoes: int


class ContextMerchantRow(BaseModel):
    descricao_exibicao: str
    valor: float


class ContextSpendBlock(BaseModel):
    contexto: str
    total: float
    top_estabelecimentos: list[ContextMerchantRow]


class NatureSpendRow(BaseModel):
    natureza: str
    total: float
    percentual: float


class RecurrenceRow(BaseModel):
    descricao_exibicao: str
    valor_mes: float
    variacao_percentual_vs_media_3m: float | None
    transaction_ids: list[str] = Field(default_factory=list)


class CategoryComparisonRow(BaseModel):
    categoria: str
    valor_mes_atual: float
    media_tres_meses_anteriores: float
    variacao_percentual: float


class MonthMetrics(BaseModel):
    mes: str
    total_transacoes: int
    transacoes_pendentes: int
    visao_geral: OverviewMetrics
    composicao_fatura_cartao: CardCompositionMetrics
    gastos_por_categoria: list[CategorySpendRow]
    gastos_por_contexto: list[ContextSpendBlock]
    gastos_por_natureza: list[NatureSpendRow]
    recorrencias: list[RecurrenceRow]
    comparativo_categorias: list[CategoryComparisonRow] = Field(default_factory=list)


def _load_rows_for_months(processed_root: Path, month_keys: list[str]) -> list[dict]:
    rows: list[dict] = []
    for month_key in month_keys:
        for transaction in load_month_transactions(processed_root, month_key):
            rows.append(flatten_for_analysis(transaction, month_key))
    return rows


def _merchant_label(descricao: str, metodo: str) -> str:
    prefix = "[?] " if metodo == "pendente" else ""
    return f"{prefix}{descricao}"


def _run_duckdb_on_rows(rows: list[dict], mes: str, prior_months: list[str]) -> MonthMetrics:
    _assert_month_key(mes)
    for prior in prior_months:
        _assert_month_key(prior)

    if not rows:
        empty_overview = OverviewMetrics(
            total_gastos=0.0,
            total_receitas=0.0,
            saldo_liquido=0.0,
            percentual_gasto_sobre_receita=None,
        )
        return MonthMetrics(
            mes=mes,
            total_transacoes=0,
            transacoes_pendentes=0,
            visao_geral=empty_overview,
            composicao_fatura_cartao=CardCompositionMetrics(grupos=[], total_base=0.0),
            gastos_por_categoria=[],
            gastos_por_contexto=[],
            gastos_por_natureza=[],
            recorrencias=[],
            comparativo_categorias=[],
        )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as tmp:
        json.dump(rows, tmp, ensure_ascii=False)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_path = tmp.name

    report_ym = _year_month_int_from_mes(mes)
    mes_sql = mes
    json_path_sql = Path(tmp_path).as_posix().replace("'", "''")

    con = duckdb.connect(database=":memory:")
    try:
        # read_json_auto infers all-null columns as JSON; VARCHAR comparisons then fail
        # ("Malformed JSON ... Input: assinatura"). Force scalar types used in WHERE/CASE.
        con.execute(
            f"""
            CREATE TABLE tx AS
            SELECT * REPLACE (
                CAST(compromisso AS VARCHAR) AS compromisso,
                CAST(recorrencia AS VARCHAR) AS recorrencia,
                CAST(parcela_numero AS INTEGER) AS parcela_numero,
                CAST(parcela_total AS INTEGER) AS parcela_total
            ) FROM read_json_auto('{json_path_sql}')
            """
        )

        overview = con.execute(
            f"""
            SELECT
                COALESCE(SUM(CASE WHEN tipo = 'debito' AND NOT excluir_gasto THEN valor ELSE 0 END), 0) AS tg,
                COALESCE(SUM(CASE WHEN tipo = 'credito' AND NOT excluir_receita THEN valor ELSE 0 END), 0) AS tr
            FROM tx
            WHERE mes_origem = '{mes_sql}'
            """
        ).fetchone()
        total_gastos = float(overview[0] or 0)
        total_receitas = float(overview[1] or 0)
        saldo = total_receitas - total_gastos
        pct = None if total_receitas <= 0 else round(100.0 * total_gastos / total_receitas, 2)

        card_rows = con.execute(
            f"""
            WITH base AS (
                SELECT valor, compromisso, data
                FROM tx
                WHERE mes_origem = '{mes_sql}'
                  AND tipo = 'debito'
                  AND NOT excluir_gasto
                  AND meio = 'cartao_credito'
            ),
            tagged AS (
                SELECT
                    valor,
                    CASE
                        WHEN compromisso = 'assinatura' THEN 'assinatura'
                        WHEN compromisso = 'parcela'
                             AND (
                               EXTRACT(YEAR FROM CAST(data AS DATE)) * 100
                               + EXTRACT(MONTH FROM CAST(data AS DATE))
                             ) < {report_ym}
                             THEN 'parcela_anterior'
                        WHEN compromisso = 'parcela' THEN 'gasto_novo'
                        ELSE 'gasto_novo'
                    END AS grupo
                FROM base
            )
            SELECT grupo, SUM(valor) AS total
            FROM tagged
            GROUP BY 1
            """
        ).fetchall()

        rotulos = {
            "gasto_novo": "Gasto novo (à vista / parcela atual)",
            "parcela_anterior": "Parcela de compra anterior",
            "assinatura": "Assinatura",
        }
        card_map = {row[0]: float(row[1] or 0) for row in card_rows}
        total_card = sum(card_map.values())
        grupos_cartao: list[CardCompositionGroup] = []
        for chave, rotulo in rotulos.items():
            valor_grupo = card_map.get(chave, 0.0)
            pct_c = 0.0 if total_card <= 0 else round(100.0 * valor_grupo / total_card, 2)
            grupos_cartao.append(
                CardCompositionGroup(chave=chave, rotulo=rotulo, valor=round(valor_grupo, 2), percentual=pct_c)
            )

        cat_rows = con.execute(
            f"""
            SELECT
                COALESCE(NULLIF(TRIM(categoria), ''), '(sem categoria)') AS cat,
                SUM(valor) AS total,
                COUNT(*) AS qtd
            FROM tx
            WHERE mes_origem = '{mes_sql}'
              AND tipo = 'debito'
              AND NOT excluir_gasto
            GROUP BY 1
            ORDER BY total DESC
            """
        ).fetchall()
        total_cat = sum(float(row[1] or 0) for row in cat_rows)
        gastos_categoria = [
            CategorySpendRow(
                categoria=str(row[0]),
                total=round(float(row[1] or 0), 2),
                percentual=0.0 if total_cat <= 0 else round(100.0 * float(row[1] or 0) / total_cat, 2),
                quantidade_transacoes=int(row[2] or 0),
            )
            for row in cat_rows
        ]

        ctx_totals = con.execute(
            f"""
            SELECT
                COALESCE(NULLIF(TRIM(contexto), ''), '(sem contexto)') AS ctx,
                SUM(valor) AS total
            FROM tx
            WHERE mes_origem = '{mes_sql}'
              AND tipo = 'debito'
              AND NOT excluir_gasto
            GROUP BY 1
            ORDER BY total DESC
            """
        ).fetchall()

        top_ctx = con.execute(
            f"""
            WITH g AS (
                SELECT *
                FROM tx
                WHERE mes_origem = '{mes_sql}'
                  AND tipo = 'debito'
                  AND NOT excluir_gasto
            ),
            agg AS (
                SELECT
                    COALESCE(NULLIF(TRIM(contexto), ''), '(sem contexto)') AS ctx,
                    descricao_original,
                    metodo,
                    SUM(valor) AS v
                FROM g
                GROUP BY 1, 2, 3
            ),
            ranked AS (
                SELECT
                    *,
                    ROW_NUMBER() OVER (PARTITION BY ctx ORDER BY v DESC) AS rk
                FROM agg
            )
            SELECT ctx, descricao_original, metodo, v
            FROM ranked
            WHERE rk <= 3
            ORDER BY ctx, rk
            """
        ).fetchall()

        tops_by_ctx: dict[str, list[ContextMerchantRow]] = {}
        for ctx_name, descricao, metodo, valor in top_ctx:
            label = _merchant_label(str(descricao), str(metodo))
            tops_by_ctx.setdefault(str(ctx_name), []).append(
                ContextMerchantRow(descricao_exibicao=label, valor=round(float(valor or 0), 2))
            )

        gastos_contexto = [
            ContextSpendBlock(
                contexto=str(row[0]),
                total=round(float(row[1] or 0), 2),
                top_estabelecimentos=tops_by_ctx.get(str(row[0]), []),
            )
            for row in ctx_totals
        ]

        nat_rows = con.execute(
            f"""
            SELECT
                COALESCE(NULLIF(TRIM(natureza), ''), 'Não informado') AS nat,
                SUM(valor) AS total
            FROM tx
            WHERE mes_origem = '{mes_sql}'
              AND tipo = 'debito'
              AND NOT excluir_gasto
            GROUP BY 1
            ORDER BY total DESC
            """
        ).fetchall()
        total_nat = sum(float(row[1] or 0) for row in nat_rows)
        gastos_natureza = [
            NatureSpendRow(
                natureza=str(row[0]),
                total=round(float(row[1] or 0), 2),
                percentual=0.0 if total_nat <= 0 else round(100.0 * float(row[1] or 0) / total_nat, 2),
            )
            for row in nat_rows
        ]

        rec_filter = "(recorrencia = 'Fixa' OR recorrencia = 'Variável recorrente')"
        if prior_months:
            prior_in = ",".join(f"'{key}'" for key in prior_months)
            rec_query = f"""
            WITH atual AS (
                SELECT descricao_original, metodo, SUM(valor) AS valor_mes, list(id) AS transaction_ids
                FROM tx
                WHERE mes_origem = '{mes_sql}'
                  AND tipo = 'debito'
                  AND NOT excluir_gasto
                  AND {rec_filter}
                GROUP BY 1, 2
            ),
            hist AS (
                SELECT descricao_original, AVG(valor) AS media
                FROM (
                    SELECT mes_origem, descricao_original, SUM(valor) AS valor
                    FROM tx
                    WHERE mes_origem IN ({prior_in})
                      AND tipo = 'debito'
                      AND NOT excluir_gasto
                      AND {rec_filter}
                    GROUP BY 1, 2
                ) sub
                GROUP BY descricao_original
            )
            SELECT atual.descricao_original, atual.metodo, atual.valor_mes, hist.media, atual.transaction_ids
            FROM atual
            LEFT JOIN hist ON atual.descricao_original = hist.descricao_original
            """
            rec_rows = con.execute(rec_query).fetchall()
        else:
            rec_rows = con.execute(
                f"""
                SELECT descricao_original, metodo, SUM(valor) AS valor_mes, NULL::DOUBLE AS media, list(id) AS transaction_ids
                FROM tx
                WHERE mes_origem = '{mes_sql}'
                  AND tipo = 'debito'
                  AND NOT excluir_gasto
                  AND {rec_filter}
                GROUP BY 1, 2
                """
            ).fetchall()

        recorrencias = []
        for descricao, metodo, valor_mes, media, transaction_ids in rec_rows:
            valor_mes_f = float(valor_mes or 0)
            var_pct = None
            if media is not None and float(media) > 0:
                var_pct = round(100.0 * (valor_mes_f - float(media)) / float(media), 2)
            recorrencias.append(
                RecurrenceRow(
                    descricao_exibicao=_merchant_label(str(descricao), str(metodo)),
                    valor_mes=round(valor_mes_f, 2),
                    variacao_percentual_vs_media_3m=var_pct,
                    transaction_ids=list(transaction_ids) if transaction_ids else [],
                )
            )

        comparativo: list[CategoryComparisonRow] = []
        if len(prior_months) >= 2:
            prior_in = ",".join(f"'{key}'" for key in prior_months)
            comp_query = f"""
            WITH hist_month AS (
                SELECT
                    mes_origem,
                    COALESCE(NULLIF(TRIM(categoria), ''), '(sem categoria)') AS cat,
                    SUM(valor) AS t
                FROM tx
                WHERE mes_origem IN ({prior_in})
                  AND tipo = 'debito'
                  AND NOT excluir_gasto
                GROUP BY 1, 2
            ),
            hist_avg AS (
                SELECT cat, AVG(t) AS media
                FROM hist_month
                GROUP BY cat
            ),
            cur AS (
                SELECT
                    COALESCE(NULLIF(TRIM(categoria), ''), '(sem categoria)') AS cat,
                    SUM(valor) AS total
                FROM tx
                WHERE mes_origem = '{mes_sql}'
                  AND tipo = 'debito'
                  AND NOT excluir_gasto
                GROUP BY 1
            )
            SELECT
                cur.cat,
                cur.total,
                hist_avg.media,
                100.0 * (cur.total - hist_avg.media) / NULLIF(hist_avg.media, 0) AS var_pct
            FROM cur
            LEFT JOIN hist_avg ON cur.cat = hist_avg.cat
            ORDER BY ABS(
                COALESCE(100.0 * (cur.total - hist_avg.media) / NULLIF(hist_avg.media, 0), 0)
            ) DESC
            """
            comp_rows = con.execute(comp_query).fetchall()
            for cat, total, media, var_pct in comp_rows:
                comparativo.append(
                    CategoryComparisonRow(
                        categoria=str(cat),
                        valor_mes_atual=round(float(total or 0), 2),
                        media_tres_meses_anteriores=round(float(media or 0), 2) if media is not None else 0.0,
                        variacao_percentual=round(float(var_pct or 0), 2) if var_pct is not None else 0.0,
                    )
                )

        tx_count = con.execute(
            f"SELECT COUNT(*) FROM tx WHERE mes_origem = '{mes_sql}'",
        ).fetchone()[0]
        pend_count = con.execute(
            f"SELECT COUNT(*) FROM tx WHERE mes_origem = '{mes_sql}' AND metodo = 'pendente'",
        ).fetchone()[0]

        return MonthMetrics(
            mes=mes,
            total_transacoes=int(tx_count or 0),
            transacoes_pendentes=int(pend_count or 0),
            visao_geral=OverviewMetrics(
                total_gastos=round(total_gastos, 2),
                total_receitas=round(total_receitas, 2),
                saldo_liquido=round(saldo, 2),
                percentual_gasto_sobre_receita=pct,
            ),
            composicao_fatura_cartao=CardCompositionMetrics(
                grupos=grupos_cartao,
                total_base=round(total_card, 2),
            ),
            gastos_por_categoria=gastos_categoria,
            gastos_por_contexto=gastos_contexto,
            gastos_por_natureza=gastos_natureza,
            recorrencias=recorrencias,
            comparativo_categorias=comparativo,
        )
    finally:
        con.close()
        Path(tmp_path).unlink(missing_ok=True)


def compute_month(
    mes: str,
    *,
    project_root: Path | None = None,
) -> MonthMetrics:
    """
    Agrega transações classificadas do mês (merge via transaction_store) e calcula métricas no DuckDB.
    """
    root = project_root or _project_root_default()
    processed_root = root / "data" / "processed"
    prior_months = _prior_month_keys(processed_root, mes, 3)
    month_keys = sorted(set(prior_months + [mes]))
    rows = _load_rows_for_months(processed_root, month_keys)
    return _run_duckdb_on_rows(rows, mes, prior_months)


def save_metrics_json(month_dir: Path, metrics: MonthMetrics) -> Path:
    month_dir.mkdir(parents=True, exist_ok=True)
    path = month_dir / f"metrics_{metrics.mes}.json"
    with path.open("w", encoding="utf-8") as handle:
        handle.write(metrics.model_dump_json(indent=2))
    return path
