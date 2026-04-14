# Classificação Multidimensional de Transações Financeiras

## O problema da categoria única

A abordagem tradicional de controle financeiro atribui **uma categoria** por transação. Uma corrida de Uber vira "Transporte". Um jantar vira "Alimentação".

Essa simplificação responde *o que* foi gasto, mas não responde as perguntas que realmente importam para decisão:

- Quanto custa minha operação fora da sede?
- Qual percentual dos meus gastos é estrutural versus discricionário?
- Quanto estou comprometendo hoje de orçamento futuro?

Para responder essas perguntas, uma transação precisa ser descrita por **múltiplas dimensões independentes**.

---

## As dimensões

| Dimensão | Pergunta que responde | Exemplos |
|---|---|---|
| **Categoria** | O que foi adquirido? | Transporte, Alimentação, Moradia, Saúde |
| **Natureza** | Por que foi adquirido? | Essencial, Discricionário, Investimento |
| **Contexto** | Dentro de qual atividade? | Operação sede, Visita cliente SP, Evento RH |
| **Recorrência** | Com que frequência ocorre? | Fixa, Variável recorrente, Pontual |
| **Compromisso** | Quando foi decidido? | À vista, Parcelado, Assinatura |
| **Meio** | Como foi executado? | Cartão corporativo, Reembolso, Direto |

Cada dimensão é **ortogonal** — pode ser combinada livremente com qualquer valor das outras. Isso transforma uma transação de um rótulo em um vetor, permitindo agregações por qualquer eixo.

---

## Exemplo: a mesma transação, contextos diferentes

Considere duas corridas de Uber de R$ 45,00, no mesmo trecho, para a mesma pessoa:

```
Transação A                          Transação B
─────────────────────────────────    ─────────────────────────────────
Categoria:   Transporte              Categoria:   Transporte
Natureza:    Essencial               Natureza:    Discricionário
Contexto:    Operação sede           Contexto:    Confraternização equipe
Recorrência: Variável recorrente     Recorrência: Pontual
Compromisso: À vista                 Compromisso: À vista
Meio:        Cartão corporativo      Meio:        Reembolso
```

O valor é idêntico. A categoria é idêntica. Mas as duas transações respondem a perguntas completamente diferentes:

- **A** entra no custo operacional recorrente da equipe
- **B** entra no orçamento de cultura e engajamento

Num modelo de categoria única, ambas somam para "Transporte" e a distinção se perde.

---

## O que isso habilita

Com dimensões independentes, qualquer combinação vira uma query válida:

- **Por contexto** → custo total de cada projeto, cliente ou evento, independente de categoria ou meio de pagamento
- **Por natureza** → separação entre o que é estrutural (não negociável) e o que é discricionário (gerenciável)
- **Por compromisso** → visibilidade do orçamento já comprometido em períodos futuros via parcelamentos
- **Por recorrência** → distinção entre baseline mensal previsível e gastos pontuais que distorcem análises

---

## Princípio central

> Uma transação financeira não é um fato atômico — é um evento que acontece simultaneamente em múltiplos eixos de análise. Modelá-la com uma única dimensão é escolher antecipadamente qual pergunta importa, descartando todas as outras.