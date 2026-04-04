# MoneyTree

## Visão geral

O **MoneyTree** é uma ferramenta de controle financeiro pessoal focada em extrair transações de PDFs de banco (hoje com suporte Itaú — fatura de cartão e extrato), classificá-las com regras e opcionalmente LLM, e consolidar **métricas mensais**, **anomalias** e um **relatório em Markdown**. O objetivo é fechar o mês com visão clara de gastos por categoria, contexto e natureza, sem planilhas manuais repetitivas.

## Arquitetura

```
moneytree/
├── backend/                 # Aplicação Python (CLI + API FastAPI)
│   ├── api/                 # Rotas REST consumidas pelo frontend
│   ├── parsers/             # Parsers por banco (BaseParser + registry)
│   ├── classifier/          # Regras, contexto, recorrência, LLM, revisão CSV
│   ├── analyzer/            # Métricas DuckDB, anomalias, relatório MD
│   ├── transaction_store/   # Merge fatura + extrato + classificação (overlay)
│   ├── models/              # Pydantic (Transaction, Classificacao, …)
│   ├── config/              # perfil.json, regras.json, taxonomia.json
│   ├── data/                # raw/ (PDFs) e processed/{mes}/ (JSONs)
│   ├── main.py              # Atalho: python main.py (adiciona raiz do repo ao path)
│   ├── cli.py               # Implementação da CLI (comando moneytree)
│   └── pyproject.toml
├── frontend/                # SPA (Vite + React) — dashboard, upload, transações
├── tests/                   # Pytest
└── README.md
```

Fluxo resumido: PDFs em `backend/data/raw/` → **parse** grava `fatura.json` / `extrato.json` → **classify** atualiza `classificacao_{mes}.json` → **analyze** gera `metrics_{mes}.json` e `report_{mes}.md`. A API lê os mesmos arquivos em `data/processed/`.

## Pré-requisitos

- **Python** 3.11+ (o projeto declara `>=3.10` no pacote)
- **Node.js** 18+
- **Opcional:** [Ollama](https://ollama.com/) com modelo `qwen2.5:7b` (ou outro configurado) para classificação local

## Instalação

```bash
# Backend — a partir da pasta backend/
cd backend
pip install -e ".[llm]"   # inclui anthropic e openai
# ou apenas:
pip install -e .          # sem extras de LLM na nuvem

# Equivalente a partir da raiz do repositório:
# pip install -e "./backend[llm]"   # ou pip install -e "./backend"

# Frontend
cd ../frontend
npm install
```

## Configuração

### `backend/config/perfil.json`

Defina contas próprias, pessoas conhecidas, cidades base e viagens — o **motor de contexto** do classificador usa esse arquivo para rotular `contexto` (ex.: “Rotina Campinas”, “Trabalho SP”, “Viagem Maceió”). Ajuste os valores à sua realidade; sem isso, o contexto tende a cair em genéricos.

### Variáveis de ambiente

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `MONEYTREE_LLM_PROVIDER` | *(definido no código / perfil)* | `ollama`, `anthropic` ou `openai` conforme implementação do cliente LLM |
| `ANTHROPIC_API_KEY` | — | Chave da API Anthropic (se usar Claude) |
| `OPENAI_API_KEY` | — | Chave da API OpenAI |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Base URL do Ollama |
| `OLLAMA_MODEL` | *(ex.: qwen2.5:7b)* | Nome do modelo no Ollama |
| `VITE_API_URL` | `http://localhost:8000` | Origem da API (sem barra final); o frontend chama `{VITE_API_URL}/api/...` |

## Uso — fluxo completo mês a mês

```bash
# 1. Adicionar PDFs
cp fatura.pdf extrato.pdf backend/data/raw/

# 2. Parsear
cd backend && python main.py parse --input ./data/raw/

# 3. Classificar (com ou sem LLM)
python main.py classify --mes 2026-03
python main.py classify --mes 2026-03 --no-llm   # só regras / pipeline sem LLM

# 4. Revisar pendências (editar CSV, depois aplicar)
python main.py review --mes 2026-03
python main.py apply-review --mes 2026-03

# 5. Gerar relatório
python main.py analyze --mes 2026-03
```

## Rodando localmente (backend + frontend)

Na raiz do repositório, após `pip install -e "./backend[dev]"` (ou com extras que precisar):

```bash
# Terminal 1 — API (qualquer diretório, com o pacote instalado em modo editável)
uvicorn backend.api.main:app --reload

# Terminal 2
cd frontend
npm run dev
# Abrir http://localhost:5173
```

CORS da API inclui `http://localhost:5173` e `http://127.0.0.1:5173`.

## Adicionando suporte a outro banco

1. Crie um pacote sob `backend/parsers/banks/{banco}/` com módulos `fatura.py` e/ou `extrato.py`.
2. Implemente uma classe que herde `backend.parsers.base_parser.BaseParser` e produza `Transaction` com `fonte`, `meio` e metadados coerentes.
3. Registre o parser em `backend/parsers/registry.py` (estrutura `_REGISTRY` / função de resolução por PDF), apontando para o factory correto e o “bucket” (`fatura` ou `extrato`).

## Estrutura dos dados processados (`backend/data/processed/{YYYY-MM}/`)

| Arquivo | Conteúdo |
|---------|-----------|
| `fatura.json` | Lista de transações extraídas da fatura do cartão |
| `extrato.json` | Lista de transações do extrato (débito/crédito, PIX, etc.) |
| `classificacao_{mes}.json` | Overlay `by_id` com classificação confirmada ou ajustada |
| `metrics_{mes}.json` | Snapshot Pydantic das métricas do mês (consumo futuro do frontend) |
| `report_{mes}.md` | Relatório Markdown gerado pelo analyzer |
| `review.csv` | CSV de revisão humana (quando usar o fluxo `review` / `apply-review`) |

## Validação rápida de imports

```bash
python -c "from backend.api.main import app; print(app.title)"
```

## Licença

Veja o repositório para a licença aplicável ao projeto.
