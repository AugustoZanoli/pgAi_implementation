#!/usr/bin/env python3
"""Leitor de query do usuario com busca semantica sobre a tabela `blogs`.

Este script le uma pergunta do usuario, gera o embedding da pergunta usando o
Ollama (via a funcao SQL `ai.ollama_embed`, executada dentro do Postgres) e
busca os artigos mais parecidos na tabela de embeddings mantida pelo pgai
(`blogs_embedding_storage`).

Alem do resultado, cada artigo vem com a **porcentagem de proximidade** em
relacao a pergunta. Ela e derivada da distancia de cosseno do pgvector
(operador `<=>`):

    similaridade_cosseno = 1 - distancia_cosseno
    proximidade (%)      = max(0, similaridade_cosseno) * 100

Como todo o embedding acontece no banco (nada de chamar o Ollama direto daqui),
o script so precisa de uma conexao Postgres.

Uso:
    python main.py                          # entra em modo interativo (REPL)
    python main.py "sua pergunta aqui"      # roda uma unica busca
    python main.py "pergunta" --limit 5     # controla quantos resultados voltam

Variaveis de ambiente lidas (com defaults):
    DB_URL              string de conexao completa (tem prioridade se definida)
    POSTGRES_USER       (default: postgres)
    POSTGRES_PASSWORD   (default: postgres)
    POSTGRES_DB         (default: pgai_ollama)
    POSTGRES_HOST       (default: localhost)
    POSTGRES_HOST_PORT  (default: 5433)
    EMBEDDING_MODEL     (default: nomic-embed-text)  -- deve bater com o vectorizer
    OLLAMA_HOST         (default: http://ollama:11434) -- visto de dentro do Postgres
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from typing import List, Optional

# O modelo de embedding precisa ser o MESMO usado no vectorizer
# (003_create_vectorizer.sql), senao a comparacao de vetores fica invalida.
DEFAULT_EMBEDDING_MODEL = "nomic-embed-text"
# Host do Ollama a partir da perspectiva do Postgres. Dentro do docker-compose
# o Postgres alcanca o Ollama pelo nome do servico ('ollama').
DEFAULT_OLLAMA_HOST = "http://ollama:11434"
DEFAULT_LIMIT = 5


def get_db_url() -> str:
    """Monta a URL de conexao a partir do ambiente (ou usa DB_URL direto)."""
    explicit = os.getenv("DB_URL")
    if explicit:
        return explicit
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    db = os.getenv("POSTGRES_DB", "pgai_ollama")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_HOST_PORT", "5433")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


@dataclass
class SearchResult:
    """Um artigo retornado pela busca semantica.

    proximity_pct: quao perto o chunk esta da pergunta, em % (0 a 100).
    distance: distancia de cosseno bruta do pgvector (0 = identico).
    """
    id: int
    title: Optional[str]
    date: Optional[str]
    chunk: str
    distance: float
    proximity_pct: float

    def __str__(self) -> str:
        title = self.title or "(sem titulo)"
        preview = self.chunk.strip().replace("\n", " ")
        if len(preview) > 160:
            preview = preview[:160] + "..."
        return (
            f"[{self.proximity_pct:5.1f}% proximo] "
            f"#{self.id} {title}\n"
            f"    {preview}"
        )


def search(conn, query: str, limit: int, model: str, ollama_host: str) -> List[SearchResult]:
    """Busca os `limit` artigos mais proximos da `query`.

    O embedding da pergunta e gerado dentro do Postgres via `ai.ollama_embed`,
    e a comparacao usa o operador de distancia de cosseno do pgvector (<=>).
    A proximidade em % vem de (1 - distancia) * 100, com piso em 0.
    """
    # Consulta a VIEW `blogs_embedding` (nao a tabela `_store`): a view junta os
    # embeddings com a tabela de origem `blogs`, entao expoe title/date/id.
    sql = """
        WITH q AS (
            SELECT ai.ollama_embed(%(model)s, %(query)s, host => %(host)s) AS embedding
        )
        SELECT
            e.id,
            e.title,
            e.date,
            e.chunk,
            (e.embedding <=> q.embedding)                        AS distance,
            GREATEST(0.0, 1.0 - (e.embedding <=> q.embedding)) * 100 AS proximity_pct
        FROM blogs_embedding e, q
        ORDER BY distance
        LIMIT %(limit)s;
    """
    with conn.cursor() as cur:
        cur.execute(
            sql,
            {"model": model, "query": query, "host": ollama_host, "limit": limit},
        )
        rows = cur.fetchall()

    return [
        SearchResult(
            id=row[0],
            title=row[1],
            date=row[2],
            chunk=row[3],
            distance=float(row[4]),
            proximity_pct=float(row[5]),
        )
        for row in rows
    ]


def print_results(query: str, results: List[SearchResult]) -> None:
    print(f'\nBusca: "{query}"')
    if not results:
        print("Nenhum resultado. A tabela de embeddings ja foi populada pelo worker?")
        return
    print(f"{len(results)} resultado(s), do mais proximo ao menos proximo:\n")
    for r in results:
        print(r)
        print()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Leitor de query com busca semantica sobre a tabela blogs (Ollama + pgai).",
    )
    parser.add_argument(
        "query",
        nargs="?",
        default=None,
        help="Pergunta a buscar. Se omitida, entra em modo interativo.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Numero maximo de artigos a retornar (default: {DEFAULT_LIMIT}).",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
        help="Modelo de embedding do Ollama (precisa bater com o vectorizer).",
    )
    parser.add_argument(
        "--ollama-host",
        default=os.getenv("OLLAMA_HOST", DEFAULT_OLLAMA_HOST),
        help="Host do Ollama visto de dentro do Postgres.",
    )
    parser.add_argument(
        "--db-url",
        default=None,
        help="URL de conexao Postgres. Se omitida, monta a partir do ambiente.",
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

    # Carrega .env se python-dotenv estiver disponivel (opcional).
    try:
        import dotenv

        dotenv.load_dotenv()
    except ImportError:
        pass

    db_url = args.db_url or get_db_url()

    try:
        conn = psycopg.connect(db_url)
    except Exception as exc:  # pragma: no cover
        print(f"Nao foi possivel conectar ao Postgres ({db_url}): {exc}", file=sys.stderr)
        return 1

    try:
        if args.query is not None:
            # Modo single-shot: uma busca e sai.
            results = search(conn, args.query, args.limit, args.model, args.ollama_host)
            print_results(args.query, results)
            return 0

        # Modo interativo (REPL).
        print("Leitor de query semantica (Ollama + pgai). Ctrl-D ou 'sair' para encerrar.")
        while True:
            try:
                query = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not query:
                continue
            if query.lower() in {"sair", "exit", "quit"}:
                break
            try:
                results = search(conn, query, args.limit, args.model, args.ollama_host)
            except Exception as exc:  # pragma: no cover
                print(f"Erro na busca: {exc}", file=sys.stderr)
                # Rollback para nao deixar a conexao em estado abortado.
                conn.rollback()
                continue
            print_results(query, results)
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
