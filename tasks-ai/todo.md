# TODO

- [x] Mapear o fluxo de upload e confirmar como o PDF do Itaú é roteado até o parser.
- [x] Reproduzir o problema com o PDF informado e identificar a causa raiz da ausência de transações.
- [x] Implementar a correção mínima e elegante no backend/upload/parser.
- [x] Adicionar ou ajustar testes cobrindo o caso do PDF enviado pelo frontend.
- [x] Validar o fluxo completo e registrar o resultado desta investigação.
- [x] Inspecionar a arquitetura atual de jobs/pipeline/API/frontend e definir o contrato desejado de status.
- [x] Separar jobs de extração e classificação, mantendo também um job acoplado de pipeline completo.
- [x] Enriquecer o payload do job com tipo, step atual e contadores de progresso para o frontend.
- [x] Expor novos endpoints para iniciar extração isolada e classificação isolada.
- [x] Adaptar a tela de upload para permitir extrair, classificar ou extrair+classificar com feedback detalhado.
- [x] Adicionar testes e validar o fluxo completo.
- [x] Inspecionar o fluxo atual de transações, edição/classificação e geração de IDs.
- [x] Separar identidade estável da transação para suportar deduplicação e vínculo entre parcelas.
- [x] Permitir reclassificar transações já classificadas no frontend.
- [x] Melhorar o modal de classificação com criação inline de categorias, naturezas, recorrências e contextos.
- [x] Validar backend/frontend após a refatoração.

# Review

- Causa raiz: o parser de fatura usava `extract_text()` sobre um crop da coluna esquerda. No PDF `Fatura_Itau_20260414-212309.pdf`, esse caminho truncava os valores (`359,80` virava `359`) e ainda cortava o token do valor em parte das linhas, produzindo zero transações.
- Correção: migramos a extração da fatura para `extract_words()` + agrupamento por linha, preservando os tokens e mantendo o isolamento da coluna esquerda.
- Reforço: linhas de `PAGAMENTO EFETUADO` com prefixo de data (`02/03 PAGAMENTOEFETUADO7426 ...`) agora também são ignoradas.
- Verificação: `tests/test_parsers.py` passou com `14 passed`, e o PDF real passou de `0` para `73` transações extraídas no parser.
- Próximo passo: evoluir o modelo de jobs para suportar orquestração desacoplada de extração e classificação com progresso consumível pelo frontend.
- Jobs: agora existem jobs distintos de `extract`, `classify` e `pipeline`, todos com `kind`, `current_step` e `counters` no payload retornado pela API.
- Progresso: o backend atualiza `files_total`, `files_processed`, `transactions_extracted`, `transactions_classified`, `transactions_pending` e `transactions_review` ao longo do job; a classificação também expõe avanço durante a etapa de LLM.
- Frontend: a tela de upload agora permite escolher `Só extrair`, `Extrair + classificar` ou `Classificar mês`, e exibe step atual e contadores de progresso.
- Validação: `pytest tests/test_parsers.py tests/test_jobs.py -q` passou com `16 passed`; `python -m py_compile ...` passou; `npm run build` passou.
- Identidade estável: transações parseadas agora recebem `id` determinístico e, quando parceladas, também `compra_id` para ligar parcelas da mesma compra em meses diferentes.
- Deduplicação: listas carregadas e JSONs escritos passam por deduplicação por `id`, reduzindo o risco de duplicar transações ao reenviar a mesma fatura.
- Reclassificação: a tela de transações agora abre itens já classificados por padrão, permite salvar reclassificação e navega pelo conjunto visível, não só pelos pendentes.
- UX do modal: o modal ganhou contexto visual da compra parcelada e criação inline de `categoria`, `natureza`, `recorrência` e `contexto`.
- Validação adicional: `pytest tests/test_parsers.py tests/test_jobs.py tests/test_classifier.py tests/test_analyzer.py tests/test_transactions_identity.py -q` passou com `31 passed`; `npm run build` continuou verde.
