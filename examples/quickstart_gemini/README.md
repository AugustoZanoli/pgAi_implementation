# Quickstart Gemini — RAG com pgai + Gemini

Exemplo de **RAG (Retrieval-Augmented Generation)** sobre artigos da Wikipedia usando [pgai](https://github.com/timescale/pgai) + [pgvector](https://github.com/pgvector/pgvector), com embeddings e geração de texto pelo **Gemini** (via [litellm](https://github.com/BerriAI/litellm)).

Diferente do exemplo do Ollama (que usa `docker-compose` + worker em container), aqui o `src/main.py` é **autocontido**: ele instala o pgai, cria o schema e o vectorizer, carrega os dados, roda o worker do pgai embarcado e faz busca + RAG, tudo num único processo Python.

## Como funciona

O `src/main.py` executa o fluxo completo:

1. Instala os componentes do pgai no banco (`pgai.install`, schema `ai`).
2. Cria a tabela `wiki` (`id`, `url`, `title`, `text`) e um **vectorizer** que embeda a coluna `text` com `gemini/gemini-embedding-001` (768 dimensões), destino `wiki_embedding_storage`.
3. Carrega 10 artigos da Wikipedia (dataset `wikimedia/wikipedia` da Hugging Face, em modo streaming).
4. Roda o `Worker` do pgai uma vez (`once=True`) para gerar os embeddings.
5. Faz busca por similaridade vetorial (operador `<=>` do pgvector) — ex.: *"Who is the father of computer science?"*.
6. Insere um artigo sobre o próprio pgai, reprocessa os embeddings e busca de novo.
7. Faz **RAG**: pega os trechos mais relevantes como contexto e gera a resposta final com o modelo de chat do Gemini.

> O modelo de embedding e o modelo de chat ficam no topo do `main.py`, em `EMBEDDING_MODEL` / `EMBEDDING_DIMENSIONS` / `CHAT_MODEL`. O mesmo modelo e o mesmo número de dimensões precisam ser usados na indexação (vectorizer) e na consulta, senão a comparação de vetores fica inválida.

## Pré-requisitos

- Python 3.10+
- PostgreSQL com as extensões **pgai** e **pgvector** (a forma mais simples é a imagem `timescale/timescaledb-ha:pg17`)
- Uma chave de API do Google (Gemini) para gerar embeddings e completar o chat

### Subir um Postgres rápido com pgai

```bash
docker run -d --name pgai-gemini \
  -p 5432:5432 \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=postgres \
  timescale/timescaledb-ha:pg17
```

## Configuração

Crie um arquivo `.env` nesta pasta (`examples/quickstart_gemini/`). Ele já está coberto pelo `.gitignore` do projeto.

```env
GOOGLE_API_KEY=sua_chave_do_google_aqui
DB_URL=postgresql://postgres:postgres@localhost:5432/postgres
```

| Variável         | Descrição                                                                 |
| ---------------- | ------------------------------------------------------------------------- |
| `GOOGLE_API_KEY` | Chave de API do Google usada pelo litellm para o Gemini (embedding + chat) |
| `DB_URL`         | String de conexão do Postgres onde o pgai está instalado                  |

> O nome da variável de chave (`GOOGLE_API_KEY`) precisa bater com o `api_key_name` definido no vectorizer (`main.py` e `resources/db/migrations/001_create_wiki.sql`).
>
> Se `DB_URL` não for definida, o `main.py` usa o default `postgresql://postgres:postgres@localhost:5432/postgres`.

## Instalação

A partir de `examples/quickstart_gemini/`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r resources/requirements.txt
```

## Execução

Com o Postgres no ar e o `.env` configurado:

```bash
python src/main.py
```

O script vai:

- imprimir os resultados de uma busca por similaridade (*"Who is the father of computer science?"*);
- inserir um artigo sobre o próprio pgai e reprocessar os embeddings;
- fazer uma nova busca (*"What is pgai?"*);
- gerar uma resposta final via RAG (*"What is the main thing pgai does right now?"*).

## Estrutura

```
quickstart_gemini/
├── resources/
│   ├── db/
│   │   └── migrations/
│   │       └── 001_create_wiki.sql   # tabela wiki + vectorizer (referência SQL)
│   └── requirements.txt              # dependências Python
├── src/
│   └── main.py                       # fluxo completo do RAG com pgai + Gemini
└── README.md
```

> Observação: `main.py` cria a tabela e o vectorizer programaticamente (em `define_schema` e `create_vectorizer`), então rodar o script não depende de aplicar o `001_create_wiki.sql` à mão — o SQL serve como referência do schema.

## Detalhes de configuração

- **Modelo de embedding:** `gemini/gemini-embedding-001` com 768 dimensões, usado no vectorizer e na query.
- **Modelo de chat (RAG):** definido em `CHAT_MODEL` no `main.py`.
- **Pool de conexões:** `psycopg_pool.AsyncConnectionPool`, aberto com `wait=True` para falhar rápido se o banco estiver inacessível.
- **Worker:** roda com `once=True` (processa a fila e para). Em produção, rodaria continuamente em background.

## Referências

- [pgai](https://github.com/timescale/pgai)
- [pgvector](https://github.com/pgvector/pgvector)
- [litellm](https://github.com/BerriAI/litellm)
