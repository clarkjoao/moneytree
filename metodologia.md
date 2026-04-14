# MoneyTree — Metodologia de Controle Financeiro Pessoal

## O problema que estamos resolvendo

Controle financeiro pessoal falha por um motivo central: **falta de visibilidade consolidada**. Faturas de cartão misturam gastos do mês atual com parcelamentos assumidos há meses. Extratos misturam despesas reais com transferências internas. Pix para pessoas físicas não dizem nada sobre o que representam. O resultado é que no fim do mês você sabe *quanto* gastou, mas não *por quê* nem *onde*.

O MoneyTree parte de uma premissa diferente: antes de categorizar, é preciso **modelar a realidade financeira com múltiplas dimensões independentes**. Uma transação não é apenas "Alimentação" — ela é alimentação, essencial, pontual, à vista, no contexto de uma viagem de trabalho, paga no cartão de crédito.

---

## Modelo de dados central

Cada transação é descrita por **seis dimensões ortogonais**, que podem ser combinadas livremente para responder qualquer pergunta:

| Dimensão | O que descreve | Exemplos |
|---|---|---|
| **Categoria** | O que foi comprado | Alimentação, Saúde, Transporte, Lazer |
| **Natureza** | Por que foi comprado | Essencial, Lazer, Investimento, Imposto |
| **Recorrência** | Com que frequência acontece | Fixa, Variável recorrente, Pontual |
| **Compromisso** | Quando foi assumido | À vista, Parcela, Assinatura |
| **Contexto** | Dentro de qual rotina | Rotina Campinas, Trabalho SP, Viagem |
| **Meio** | Como foi pago | Cartão de crédito, Débito/Pix |

A separação entre **natureza** e **categoria** é deliberada. Um jantar pode ser Alimentação/Essencial (almoço de trabalho) ou Alimentação/Lazer (comemoração). Um mesmo estabelecimento pode ter naturezas diferentes dependendo da circunstância — e o sistema permite isso.

---

## A dimensão mais importante: Compromisso

A pergunta mais difícil sobre o cartão de crédito não é "quanto gastei?" mas **"quanto desse valor eu já tinha decidido gastar antes deste mês?"**

O campo `compromisso` responde isso:

```
Fatura do mês = À vista (decisão deste mês)
              + Parcelas (decisão de meses anteriores)
              + Assinaturas (recorrente, assumido no passado)
```

Quando a parcela 2/4 de um eletrodoméstico aparece na fatura de março, ela não é um gasto de março — é um compromisso assumido em janeiro. O MoneyTree trata isso como dado estruturado, não como texto. Isso permite visualizar exatamente qual percentual da fatura representa **descontrole potencial** (à vista do mês) versus **compromissos já assumidos**.

---

## Contexto: a dimensão geográfica e situacional

Muitos gastos só fazem sentido dentro de um contexto. Uma corrida de Uber pode ser deslocamento de trabalho em SP ou lazer em Campinas. Um hotel é sempre viagem. Gasolina pode ser rotina ou deslocamento profissional.

O MoneyTree infere contexto por hierarquia de confiança:

1. **Cidade no nome do estabelecimento** (`.SAO PAULO`, `.MACEIO`) → confiança alta, aplica automaticamente
2. **Estabelecimentos âncora** (LATAM, AIRBNB, HOTEL) → sempre viagem
3. **Janela de datas de viagem** definida no perfil → transações dentro do período recebem o contexto da viagem
4. **Contexto padrão** → tudo que não se encaixa acima

Isso permite consolidar o custo real de uma viagem de trabalho somando hotel (cartão), gasolina (Pix), alimentação fora (cartão) e Uber (cartão) — independente do meio de pagamento.

---

## Pipeline de processamento

```
PDF (fatura + extrato)
       │
       ▼
  [1] PARSE
  pdfplumber extrai transações brutas
  MarkItDown como fallback para páginas mal formatadas
  Filtra metadados: pagamento de fatura, saldo do dia, rendimentos
       │
       ▼
  [2] REGRAS DETERMINÍSTICAS
  Match exato ou substring contra regras.json
  Pessoas físicas mapeadas em perfil.json
  Contas próprias → Transferência Interna (excluída dos totais)
  Cobertura esperada: ~20% no primeiro mês, ~80% após 3 meses
       │
       ▼
  [3] CONTEXT ENGINE
  Infere campo `contexto` independente da categoria
  Enriquece tanto transações classificadas por regra quanto pendentes
       │
       ▼
  [4] LLM (opcional)
  Apenas para transações ainda pendentes
  Lotes de 20, system prompt com taxonomia + perfil
  Retorna confiança por transação
  Agnóstico ao provedor: Anthropic, OpenAI, Ollama
       │
       ▼
  [5] DETECÇÃO DE RECORRÊNCIA
  DuckDB sobre janela de 60 dias de histórico
  Sugere Fixa (desvio < 10%) ou Variável recorrente
  Caso especial: Pix para pessoas físicas recorrentes → sugestão de mapeamento
       │
       ▼
  [6] REVISÃO HUMANA
  CSV com transações de confiança < 0.75 ou ainda pendentes
  Confirmações retroalimentam regras.json (aprendizado)
  Método "confirmado" → confiança 1.0, nunca volta para revisão
       │
       ▼
  [7] ANÁLISE
  DuckDB agrega métricas sobre transações classificadas
  Relatório Markdown + metrics.json para o frontend
```

---

## Separação de responsabilidades nos dados

Uma decisão arquitetural importante: **parse e classificação são dados imutáveis separados**.

```
data/processed/2026-03/
├── fatura.json              ← transações brutas do cartão (imutável após parse)
├── extrato.json             ← transações brutas do extrato (imutável após parse)
├── classificacao_2026-03.json  ← overlay de classificações (pode ser re-gerado)
├── metrics_2026-03.json     ← métricas calculadas
├── review.csv               ← pendentes para revisão humana
├── suggestions.json         ← sugestões de recorrência
└── report_2026-03.md        ← relatório legível
```

Se o parser tiver um bug e precisar ser re-executado, as classificações já confirmadas não se perdem. Se quiser re-classificar com um modelo melhor, os dados brutos estão intactos. O `transaction_store` faz o merge em memória na leitura.

---

## O ciclo de aprendizado

O sistema fica mais útil a cada mês porque **toda revisão manual se converte em regra**:

```
Mês 1: ~20% classificado por regra, ~80% revisão manual
Mês 2: ~50% por regra (aprendeu os recorrentes)
Mês 3: ~80% por regra (a maioria dos estabelecimentos já está mapeada)
Mês N: revisão manual fica apenas para estabelecimentos novos e Pix ambíguos
```

Quando o usuário confirma uma transação no review CSV ou no frontend, `append_exact_rule()` adiciona o mapeamento em `regras.json`. Na próxima vez que aquela descrição aparecer — mesmo em meses futuros — é classificada com confiança 1.0 sem passar pelo LLM.

---

## Tratamento especial: Pix para pessoas físicas

Pix para pessoas físicas é o caso mais ambíguo do controle financeiro pessoal brasileiro. `PIX TRANSF OTAVIO` pode ser:
- Pagamento do personal trainer (Saúde/Essencial/Fixa)
- Racha de jantar (Alimentação/Lazer/Pontual)
- Presente (Lazer/Pontual)
- Transferência para conta própria (Transferência Interna — excluir dos totais)

O MoneyTree trata isso em três camadas:

1. **`contas_proprias` no perfil** → tokens que identificam suas próprias contas são marcados como Transferência Interna e excluídos de todas as análises de gasto
2. **`pessoas_conhecidas` no perfil** → mapeamento permanente de nome → classificação (feito uma vez, vale para sempre)
3. **Detecção de recorrência** → se o mesmo nome aparece ≥ 2 vezes em 60 dias sem classificação, o sistema sugere que o usuário o mapeie

---

## Métricas que o sistema responde

Com a estrutura acima, é possível responder perguntas que controles tradicionais não conseguem:

**Composição da fatura:**
> "Dos R$ 4.696 desta fatura, R$ 1.850 são parcelamentos que assumi em meses anteriores. Meu gasto novo do mês foi R$ 2.846."

**Custo real de contextos:**
> "Minhas viagens de trabalho para SP custam em média R$ 1.200/mês, somando hotel, gasolina, alimentação e transporte."

**Tendências por natureza:**
> "Em março gastei 34% em Essencial, 41% em Lazer, 15% em Investimento. Em fevereiro o Lazer foi 28%."

**Recorrências fora do padrão:**
> "Farmácia este mês foi R$ 680, contra uma média de R$ 380 nos últimos 3 meses — 79% acima."

**Anomalias:**
> "3 transações individuais acima de 30% da sua média diária de gastos."

---

## O que o sistema não tenta resolver

Por decisão explícita, o MoneyTree **não**:

- Conecta diretamente com APIs bancárias — trabalha com PDFs exportados manualmente, o que mantém os dados sob controle do usuário
- Tenta classificar automaticamente com 100% de precisão — a revisão humana é parte do design, não uma limitação
- Substitui um planejamento orçamentário — ele descreve o que aconteceu, não prescreve o que deveria acontecer
- Consolida investimentos, patrimônio ou dívidas de longo prazo — o foco é fluxo de caixa mensal