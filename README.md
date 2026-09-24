# pgAi implementation

Exemplo prático de **RAG (Retrieval-Augmented Generation)** usando o [pgai](https://github.com/timescale/pgai), que transforma o PostgreSQL no motor de busca vetorial da aplicação. Os embeddings são gerados automaticamente pelo `vectorizer` do pgai e as buscas por similaridade usam o [pgvector](https://github.com/pgvector/pgvector).

O quickstart carrega artigos da Wikipedia, gera embeddings com o modelo `gemini-embedding-001` (via [litellm](https://github.com/BerriAI/litellm)), faz busca por similaridade e finaliza com uma etapa de RAG usando um modelo de chat do Gemini.

## Como funciona

1. Instala os componentes do pgai no banco (schema `ai`).
2. Cria a tabela `wiki` e um `vectorizer` que gera embeddings da coluna `text`.
3. Carrega alguns artigos da Wikipedia (dataset da Hugging Face).
4. Roda o worker do pgai para gerar os embeddings.
5. Faz busca por similaridade vetorial (operador `<=>` do pgvector).
6. Usa os trechos mais relevantes como contexto para uma resposta gerada por LLM (RAG).

## Requisitos

- Python 3.10+
- PostgreSQL com as extensões **pgai** e **pgvector** habilitadas
- Uma chave de API do Google (Gemini) para gerar embeddings e completar o chat

A forma mais simples de subir o banco com tudo pronto é usar a imagem oficial do TimescaleDB com pgai. Consulte a [documentação do pgai](https://github.com/timescale/pgai) para a configuração recomendada.

## Configuração

Crie um arquivo `.env` na raiz do projeto com as variáveis abaixo (o `.env` já está no `.gitignore`):

```env
GOOGLE_API_KEY=sua_chave_do_google_aqui
DB_URL=postgresql://usuario:senha@localhost:5432/pgai_implementation
```

| Variável         | Descrição                                                        |
| ---------------- | ---------------------------------------------------------------- |
| `GOOGLE_API_KEY` | Chave de API do Google usada pelo litellm para o Gemini          |
| `DB_URL`         | String de conexão do PostgreSQL onde o pgai está instalado       |

> O nome da variável de chave (`GOOGLE_API_KEY`) precisa bater com o `api_key_name` definido no vectorizer.

## Instalação

```bash
cd examples/quickstart
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Execução

Com o banco de dados no ar e o `.env` configurado:

```bash
cd examples/quickstart
python main.py
```

O script vai:

- imprimir os resultados de uma busca por similaridade ("Who is the father of computer science?");
- inserir um artigo sobre o próprio pgai e reprocessar os embeddings;
- fazer uma nova busca ("What is pgai?");
- gerar uma resposta final via RAG.

## Estrutura do projeto

```
pgAi/
├── db/
│   └── migrations/
│       └── 001_create_wiki.sql   # cria a tabela wiki e o vectorizer
├── examples/
│   └── quickstart/
│       ├── main.py               # fluxo completo do RAG com pgai
│       └── requirements.txt      # dependências Python
├── .env                          # variáveis de ambiente (não versionado)
└── README.md
```

## Detalhes de configuração

- **Modelo de embedding:** `gemini/gemini-embedding-001` com 768 dimensões. O mesmo modelo e o mesmo número de dimensões precisam ser usados na indexação (vectorizer) e na consulta, senão a comparação de vetores fica inválida.
- **Modelo de chat (RAG):** definido em `CHAT_MODEL` no `main.py`.
- **Pool de conexões:** usa `psycopg_pool.AsyncConnectionPool` para gerenciar conexões de forma eficiente.

## Referências

- [pgai](https://github.com/timescale/pgai)
- [pgvector](https://github.com/pgvector/pgvector)
- [litellm](https://github.com/BerriAI/litellm)
