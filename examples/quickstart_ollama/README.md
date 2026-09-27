# Quickstart Ollama — busca semântica com proximidade (%)

Exemplo de **busca semântica** sobre a tabela `blogs` usando [pgai](https://github.com/timescale/pgai) + [pgvector](https://github.com/pgvector/pgvector), com embeddings gerados por um **Ollama self-hosted** (modelo `nomic-embed-text`).

O leitor de query (`src/main.py`) lê uma pergunta do usuário e devolve os artigos mais parecidos, cada um com a **porcentagem de proximidade** em relação à pergunta.

## Como funciona

1. O `docker-compose.yml` sobe três serviços: `db` (Postgres + pgai), `vectorizer-worker` e `ollama`.
2. A tabela `blogs` é criada e populada com o dataset `sgoel9/sam_altman_essays`.
3. Um **vectorizer** (`003_create_vectorizer.sql`) embeda a coluna `text` com `nomic-embed-text` (768 dimensões). O worker gera os embeddings automaticamente e mantém:
   - a tabela de armazenamento `blogs_embedding_store`;
   - a **view** `blogs_embedding`, que junta `blogs` com os embeddings (expõe `id`, `title`, `date`, `text`, `chunk`, `embedding`, `chunk_seq`).
4. O leitor gera o embedding da pergunta **dentro do Postgres** via `ai.ollama_embed(...)` e ordena por distância de cosseno (`<=>`) do pgvector.

### Como a proximidade (%) é calculada

O pgvector retorna a **distância de cosseno** (`0` = idêntico, `2` = oposto). A proximidade é derivada dela:

```
similaridade_cosseno = 1 - distancia_cosseno
proximidade (%)      = max(0, similaridade_cosseno) * 100
```

Ou seja, quanto mais perto de 100%, mais o artigo casa com a pergunta.

## Pré-requisitos

- Docker + Docker Compose (o `db` e o `ollama` rodam em container)
- Python 3.10+ no host (para rodar o leitor e o script de população)

## Configuração

O `.env` fica em `resources/` (mesma pasta do `docker-compose.yml`), porque o Compose lê o `.env` do diretório onde o comando roda. Já existe um `resources/.env`; use o `.env.example` como referência.

| Variável             | Usado por            | Descrição                                                    |
| -------------------- | -------------------- | ------------------------------------------------------------ |
| `POSTGRES_USER`      | compose / leitor     | usuário do Postgres                                          |
| `POSTGRES_PASSWORD`  | compose / leitor     | senha do Postgres                                            |
| `POSTGRES_DB`        | compose / leitor     | nome do banco (`pgai_ollama`)                                |
| `POSTGRES_HOST_PORT` | compose / leitor     | porta publicada no host (`5433`)                             |
| `POSTGRES_HOST`      | leitor (host)        | host do Postgres visto do host (`localhost`)                 |
| `OLLAMA_HOST`        | worker / Postgres    | endereço do Ollama na rede do Compose (`http://ollama:11434`) |
| `EMBEDDING_MODEL`    | leitor               | modelo de embedding — **precisa bater com o vectorizer**     |
| `POLL_INTERVAL`      | worker               | intervalo de polling do worker (`5s`)                        |
| `VECTORIZER_WORKER_TAG` | compose           | tag da imagem do vectorizer-worker (`latest`)                |
| `DB_URL`             | leitor (opcional)    | string de conexão completa; se definida, ignora as `POSTGRES_*` |

## Passo a passo

Todos os comandos a partir de `examples/quickstart_ollama/`.

**1. Subir os serviços** (o `.env` está em `resources/`):

```bash
cd resources
docker compose up -d
```

**2. Baixar o modelo de embedding no Ollama** (só na primeira vez):

```bash
docker compose exec ollama ollama pull nomic-embed-text
```

**3. Instalar o pgai no banco e aplicar as migrations:**

```bash
# instala os componentes do pgai (schema ai) no banco
docker compose run --rm --entrypoint \
  "python -m pgai install -d postgres://postgres:postgres@db:5432/pgai_ollama" \
  vectorizer-worker

# aplica as migrations (tabela blogs + vectorizer)
docker compose exec -T db psql -U postgres -d pgai_ollama < db/migrations/000_create_table_blogs.sql
docker compose exec -T db psql -U postgres -d pgai_ollama < db/migrations/003_create_vectorizer.sql
```

**4. Popular a tabela `blogs`** (roda no host):

```bash
cd db/scripts
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python populate_blogs.py           # ou --limit N
deactivate && cd ../..
```

**5. Aguardar o worker gerar os embeddings.** Acompanhe:

```bash
docker compose logs -f vectorizer-worker
```

## Rodar o leitor de query

Do diretório `examples/quickstart_ollama/src/`:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# busca única
python main.py "o que Sam Altman fala sobre startups?"

# controlar quantos resultados voltam
python main.py "conselhos sobre foco" --limit 3

# modo interativo (REPL): digite perguntas; 'sair' para encerrar
python main.py
```

> O leitor carrega variáveis do `.env` automaticamente (se `python-dotenv` estiver instalado). Rodando de `src/`, aponte para o `.env` de `resources/` exportando as variáveis ou usando `DB_URL`, por exemplo:
> `DB_URL=postgresql://postgres:postgres@localhost:5433/pgai_ollama python main.py "sua pergunta"`

### Exemplo de saída

```
Busca: "conselhos sobre foco"
3 resultado(s), do mais proximo ao menos proximo:

[ 78.4% proximo] #12 The Days Are Long But the Decades Are Short
    Focus is underrated. It's easy to be busy and hard to be focused...

[ 71.9% proximo] #4 How To Be Successful
    ...
```

## Detalhes importantes

- **O modelo precisa ser o mesmo** na indexação (vectorizer) e na consulta (`ai.ollama_embed`), com o mesmo número de dimensões — senão a comparação de vetores fica inválida.
- O embedding da pergunta é gerado **dentro do Postgres**, então o leitor só precisa de conexão com o banco (não fala direto com o Ollama). Por isso o `OLLAMA_HOST` do leitor usa o nome de serviço do Compose (`http://ollama:11434`), que é a perspectiva do Postgres.
- A busca é feita sobre a **view** `blogs_embedding`, que traz `title`/`date`/`id` junto de cada `chunk`.

## Referências

- [pgai](https://github.com/timescale/pgai)
- [pgvector](https://github.com/pgvector/pgvector)
- [Ollama](https://ollama.com)
