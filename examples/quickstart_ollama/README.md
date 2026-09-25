# Quickstart pgai + Ollama

Exemplo ponta a ponta de busca semântica com [pgai](https://github.com/timescale/pgai),
Postgres (TimescaleDB) e [Ollama](https://ollama.com/) para gerar embeddings 100% local.

O fluxo é:

1. Subir Postgres, Ollama e o `vectorizer-worker` via Docker Compose.
2. Instalar o pgai no banco (como **schema**, não como extensão).
3. Popular a tabela `blogs` com um dataset de exemplo.
4. Criar um _vectorizer_, que gera embeddings automaticamente via Ollama.
5. Fazer busca semântica sobre os embeddings.

## Modelo atual do pgai (importante)

Versões recentes do pgai (>= 0.10) **deixaram de usar a extensão do Postgres**.
Não rode `CREATE EXTENSION ai CASCADE;` — ele falha com _"extension ai is not
available"_. O pgai passou a ser instalado como um **schema `ai`** através do CLI
`pgai install`, o que também simplifica o uso em provedores gerenciados (RDS,
Supabase, etc.).

Consequência prática: as funções que rodavam Python dentro do banco (via
`plpython3u`) **não existem** neste modelo. Ou seja, `ai.load_dataset` e
`ai.ollama_embed` não estão disponíveis. Por isso:

- a **carga do dataset** é feita por um script no host (`db/scripts/populate_blogs.py`);
- o **embedding da consulta de busca** é gerado no host chamando o Ollama
  (`db/scripts/search_blogs.py`).

A geração dos embeddings dos documentos continua automática, feita pelo
`vectorizer-worker`.

## Pré-requisitos

- Docker e Docker Compose
- Python 3.10+ (para os scripts de carga e busca)

## Estrutura

```
quickstart_ollama/
├── .env                      # variáveis de ambiente (não versionado)
├── .env.example              # modelo das variáveis
└── resources/
    ├── docker-compose.yml    # db + vectorizer-worker + ollama
    ├── .env                  # variáveis lidas pelo compose (junto do arquivo)
    ├── .env.example
    └── db/
        ├── migrations/       # SQL do schema e do vectorizer
        │   ├── 000_create_table_blogs.sql
        │   ├── 001_create_extension.sql   # (doc) valida o schema ai
        │   ├── 002_load_dataset.sql       # (doc) aponta para o script de carga
        │   └── 003_creating_vectorizer.sql
        └── scripts/
            ├── populate_blogs.py
            ├── search_blogs.py
            └── requirements.txt
```

> O `docker-compose.yml` lê o `.env` da pasta onde é executado. Por isso existe
> um `.env` em `resources/`, ao lado do compose. Rode os comandos `docker compose`
> a partir de `resources/`.

## Configuração

As variáveis ficam em `resources/.env` (copie de `.env.example`):

| Variável | Descrição | Exemplo |
|---|---|---|
| `POSTGRES_USER` | Usuário do Postgres | `postgres` |
| `POSTGRES_PASSWORD` | Senha do Postgres | `postgres` |
| `POSTGRES_DB` | Nome do banco | `pgai_ollama` |
| `POSTGRES_HOST_PORT` | Porta do Postgres no host | `5433` |
| `OLLAMA_HOST` | Endereço do Ollama para o worker (rede Docker) | `http://ollama:11434` |
| `OLLAMA_HOST_PORT` | Porta do Ollama publicada no host (para os scripts) | `11434` |
| `POLL_INTERVAL` | Intervalo de polling do worker | `5s` |
| `VECTORIZER_WORKER_TAG` | Tag da imagem do worker (precisa ter o comando `install`) | `latest` |

```bash
cp resources/.env.example resources/.env
# edite os valores conforme necessário
```

## Passo a passo

Todos os comandos `docker compose` rodam a partir de `resources/`.

### 1. Subir os serviços

```bash
cd resources
docker compose up -d
```

### 2. Baixar o modelo de embeddings no Ollama

```bash
docker compose exec ollama ollama pull nomic-embed-text
```

O volume `ollama` persiste os modelos entre recriações do container.

### 3. Instalar o pgai no banco (uma vez)

```bash
docker compose run --rm \
  --entrypoint "python -m pgai install -d postgres://postgres:postgres@db:5432/pgai_ollama" \
  vectorizer-worker
```

Isso cria o schema `ai` e suas funções. Ajuste usuário/senha/banco se você mudou o `.env`.

### 4. Aplicar as migrations

Crie a tabela e o vectorizer. As migrations `001` e `002` são documentais
(explicam o modelo novo); as que aplicam SQL de fato são a `000` e a `003`.

```bash
docker compose exec -T db psql -U postgres -d pgai_ollama \
  < db/migrations/000_create_table_blogs.sql

docker compose exec -T db psql -U postgres -d pgai_ollama \
  < db/migrations/003_creating_vectorizer.sql
```

### 5. Popular a tabela `blogs`

O script baixa o dataset `sgoel9/sam_altman_essays` do Hugging Face e insere na
tabela. Use `--recreate` se a tabela já existir com schema incompatível.

```bash
cd db/scripts
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

set -a && . ../../.env && set +a
.venv/bin/python populate_blogs.py --recreate      # 50 registros (default)
# .venv/bin/python populate_blogs.py --limit 112   # dataset completo
```

### 6. Acompanhar a vetorização

O `vectorizer-worker` processa a fila automaticamente. Acompanhe:

```bash
cd ../..                # volta para resources/
docker compose exec db psql -U postgres -d pgai_ollama \
  -c "SELECT * FROM ai.vectorizer_status;"
```

Quando `pending_items` chegar a `0`, todos os chunks foram embeddados.

### 7. Busca semântica

Gera o embedding da pergunta via Ollama (no host) e ordena os chunks por
similaridade de cosseno (`<=>`) no banco.

```bash
cd db/scripts
set -a && . ../../.env && set +a
.venv/bin/python search_blogs.py "Generative AI models" --limit 5
```

Saída (exemplo):

```
Top 5 resultados para: 'Generative AI models'
1. [0.4408] DALL•E 2
   Blog title: DALL•E 2 Publishing date: ... Blog chunk: ...
...
```

## Solução de problemas

- **`extension "ai" is not available`** — você tentou `CREATE EXTENSION ai`.
  Não use; rode o `pgai install` do passo 3.
- **`function ai.load_dataset(...) does not exist`** — essa função não existe no
  modelo atual. Use `populate_blogs.py` (passo 5).
- **`function ai.ollama_embed(...) does not exist`** — idem; a busca gera o
  embedding fora do banco via `search_blogs.py` (passo 7).
- **Itens travados em `pending`** — verifique se o `vectorizer-worker` está com
  uma tag que tenha o comando `install` (use `VECTORIZER_WORKER_TAG=latest`) e se
  o modelo `nomic-embed-text` está baixado no Ollama (passo 2). Veja os logs com
  `docker compose logs -f vectorizer-worker`.
- **Falha ao chamar o Ollama no `search_blogs.py`** — confirme que
  `OLLAMA_HOST_PORT` está publicado (`docker port pgai-ollama-1`) e acessível em
  `http://localhost:11434`.
