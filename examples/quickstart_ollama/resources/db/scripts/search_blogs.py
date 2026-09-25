"""Busca semantica nos blogs vetorizados pelo pgai.

No modelo atual do pgai (instalado via `pgai install`, sem as funcoes de
model-calling que rodam dentro do Postgres via plpython3u), nao existe
`ai.ollama_embed` no banco. Entao o embedding da pergunta e gerado aqui, no
host, chamando o Ollama diretamente. A busca por similaridade (<=>) continua
sendo feita no banco, sobre os embeddings ja gerados pelo vectorizer-worker.

Fluxo:
    1. Recebe uma consulta em linguagem natural.
    2. Gera o vetor da consulta chamando o Ollama (mesmo modelo do vectorizer).
    3. Ordena os chunks da view `blogs_embedding` por distancia de cosseno.

Uso:
    python search_blogs.py "Generative AI models"
    python search_blogs.py "startup advice" --limit 3

Variaveis de ambiente lidas (com defaults):
    POSTGRES_USER       (default: postgres)
    POSTGRES_PASSWORD   (default: postgres)
    POSTGRES_DB         (default: pgai_ollama)
    POSTGRES_HOST       (default: localhost)
    POSTGRES_HOST_PORT  (default: 5433)
    OLLAMA_URL          (default: http://localhost:11434)
    EMBEDDING_MODEL     (default: nomic-embed-text)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_MODEL = "nomic-embed-text"
DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_LIMIT = 5


def get_db_url() -> str:
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    db = os.getenv("POSTGRES_DB", "pgai_ollama")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_HOST_PORT", "5433")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def embed_query(text: str, ollama_url: str, model: str) -> list[float]:
    """Gera o embedding da consulta chamando o endpoint do Ollama."""
    payload = json.dumps({"model": model, "prompt": text}).encode("utf-8")
    req = urllib.request.Request(
        f"{ollama_url.rstrip('/')}/api/embeddings",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:  # pragma: no cover
        raise SystemExit(
            f"Falha ao chamar o Ollama em {ollama_url}: {exc}. "
            "Confirme que o Ollama esta acessivel (porta publicada no host)."
        )

    embedding = data.get("embedding")
    if not embedding:
        raise SystemExit(f"Resposta do Ollama sem embedding: {data}")
    return embedding


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Busca semantica nos blogs vetorizados.")
    parser.add_argument("query", help="Texto da consulta em linguagem natural.")
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Numero de resultados (default: {DEFAULT_LIMIT}).",
    )
    parser.add_argument(
        "--db-url",
        default=None,
        help="URL de conexao Postgres. Se omitido, monta a partir das variaveis de ambiente.",
    )
    parser.add_argument(
        "--ollama-url",
        default=os.getenv("OLLAMA_URL", DEFAULT_OLLAMA_URL),
        help=f"URL base do Ollama (default: {DEFAULT_OLLAMA_URL}).",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("EMBEDDING_MODEL", DEFAULT_MODEL),
        help=f"Modelo de embeddings (default: {DEFAULT_MODEL}).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover
        print(
            f"Dependencia ausente: {exc.name}. Instale com: pip install -r requirements.txt",
            file=sys.stderr,
        )
        return 1

    db_url = args.db_url or get_db_url()

    print(f"Gerando embedding da consulta via Ollama ({args.model})...")
    query_vector = embed_query(args.query, args.ollama_url, args.model)

    # O vetor e passado como texto no formato do pgvector: "[v1,v2,...]".
    vector_literal = "[" + ",".join(str(v) for v in query_vector) + "]"

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    title,
                    chunk,
                    embedding <=> %s::vector AS distance
                FROM blogs_embedding
                ORDER BY distance
                LIMIT %s;
                """,
                (vector_literal, args.limit),
            )
            rows = cur.fetchall()

    print(f"\nTop {len(rows)} resultados para: {args.query!r}\n")
    for i, (title, chunk, distance) in enumerate(rows, start=1):
        preview = chunk.strip().replace("\n", " ")
        if len(preview) > 200:
            preview = preview[:200] + "..."
        print(f"{i}. [{distance:.4f}] {title}")
        print(f"   {preview}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
