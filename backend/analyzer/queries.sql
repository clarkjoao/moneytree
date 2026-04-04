-- MoneyTree — queries DuckDB usadas em analyzer/metrics.py
-- Documentação viva: manter alinhado com o código Python que monta a tabela `tx`
-- via read_json_auto() sobre JSON gerado a partir de transaction_store.load_month_transactions.

-- =============================================================================
-- Tabela base `tx` (criada no Python)
-- Colunas esperadas: id, mes_origem, data, valor, tipo, meio, descricao_original,
-- fonte, categoria, natureza, recorrencia, compromisso, contexto, metodo,
-- parcela_numero, parcela_total, excluir_gasto, excluir_receita
--
-- Importante: o JSON é carregado com read_json_auto e em seguida normalizado com
-- SELECT * REPLACE (CAST compromisso/recorrencia/parcela_* para VARCHAR/INTEGER).
-- Colunas só com null no arquivo são inferidas como JSON pelo DuckDB; comparações
-- com literais VARCHAR disparam erro de JSON malformado.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Bloco 1 — Visão geral (totais do mês alvo)
-- Total de gastos: débitos que não são Transferência Interna / Receita / pagamento de fatura.
-- Total de receitas: créditos que não são transferência interna.
-- -----------------------------------------------------------------------------
-- SELECT
--   COALESCE(SUM(CASE WHEN tipo = 'debito' AND NOT excluir_gasto THEN valor ELSE 0 END), 0) AS total_gastos,
--   COALESCE(SUM(CASE WHEN tipo = 'credito' AND NOT excluir_receita THEN valor ELSE 0 END), 0) AS total_receitas
-- FROM tx
-- WHERE mes_origem = ?;

-- -----------------------------------------------------------------------------
-- Bloco 2 — Composição da fatura do cartão
-- Filtra apenas cartão de crédito + débito elegível; classifica em:
--   assinatura | parcela_anterior (YEAR*100+MONTH da compra < mês do relatório) | gasto_novo
-- -----------------------------------------------------------------------------
-- Nota: evitar strftime('%Y-%m', ...) no DuckDB com placeholders `?` — o caractere `%`
-- interage com o binder. Usar EXTRACT(YEAR/MONTH) conforme metrics.py.

-- -----------------------------------------------------------------------------
-- Bloco 3 — Gastos por categoria
-- Agrupa COALESCE(categoria,'(sem categoria)'), ordena por SUM(valor) DESC.
-- -----------------------------------------------------------------------------

-- -----------------------------------------------------------------------------
-- Bloco 4 — Gastos por contexto + top 3 estabelecimentos
-- Agrega por contexto; CTE `agg` soma por (contexto, descricao_original, metodo);
-- `ranked` usa ROW_NUMBER() PARTITION BY contexto ORDER BY valor DESC; rk <= 3.
-- -----------------------------------------------------------------------------

-- -----------------------------------------------------------------------------
-- Bloco 5 — Gastos por natureza
-- Mesmo universo de gastos elegíveis; agrupa natureza (ou 'Não informado').
-- -----------------------------------------------------------------------------

-- -----------------------------------------------------------------------------
-- Bloco 6 — Recorrências (Fixa / Variável recorrente)
-- Mês atual: soma por descrição; histórico: média das somas mensais nos 3 meses anteriores.
-- LEFT JOIN para calcular variação % vs média quando há histórico.
-- -----------------------------------------------------------------------------

-- -----------------------------------------------------------------------------
-- Bloco 7 — Comparativo de categorias (≥ 2 meses anteriores no histórico)
-- Para cada categoria: média do total mensal nos meses anteriores vs total do mês atual.
-- -----------------------------------------------------------------------------
