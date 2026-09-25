"""Popula a tabela `blogs` com o dataset sgoel9/sam_altman_essays do Hugging Face.

Este script substitui a chamada `ai.load_dataset(...)`, que nao esta disponivel
no modelo atual do pgai (instalado via `pgai install`, sem as funcoes que rodam
Python dentro do Postgres via plpython3u). Aqui o download do dataset acontece no
host e os dados sao inseridos no banco via conexao normal.

Uso:
    python populate_blogs.py                 # usa as variaveis do .env
    python populate_blogs.py --limit 100     # carrega ate 100 registros

Variaveis de ambiente lidas (com defaults):
    POSTGRES_USER       (default: postgres)
    POSTGRES_PASSWORD   (default: postgres)
    POSTGRES_DB         (default: pgai_ollama)
    POSTGRES_HOST       (default: localhost)
    POSTGRES_HOST_PORT  (default: 5433)
"""
from __future__ import annotations

import argparse
import os
import sys

DATASET = "sgoel9/sam_altman_essays"
DATASET_CONFIG = "default"
DEFAULT_LIMIT = 50  # espelha o batch_size=50, max_batches=1 do ai.load_dataset original


def get_db_url() -> str:
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    db = os.getenv("POSTGRES_DB", "pgai_ollama")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_HOST_PORT", "5433")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Popula a tabela blogs com o dataset do HF.")
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Numero maximo de registros a inserir (default: {DEFAULT_LIMIT}).",
    )
    parser.add_argument(
        "--db-url",
        default=None,
        help="URL de conexao Postgres. Se omitido, monta a partir das variaveis de ambiente.",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Dropa a tabela 'blogs' antes de criar (util quando o schema existente e incompativel).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        import psycopg
        from datasets import load_dataset
    except ImportError as exc:  # pragma: no cover
        print(
            f"Dependencia ausente: {exc.name}. "
            "Instale com: pip install -r requirements.txt",
            file=sys.stderr,
        )
        return 1

    db_url = args.db_url or get_db_url()
    recreate = args.recreate

    print(f"Baixando dataset '{DATASET}' (config '{DATASET_CONFIG}', split 'train')...")
    dataset = load_dataset(DATASET, DATASET_CONFIG, split="train")

    total = min(args.limit, len(dataset)) if args.limit else len(dataset)
    print(f"Dataset carregado: {len(dataset)} registros disponiveis. Inserindo {total}.")

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            # Recria a tabela com um schema compativel com o dataset.
            # `text` usa TEXT (sem limite) porque os essays passam de 255 chars,
            # `date` usa TEXT porque no dataset o campo e string livre, e `id`
            # e um BIGINT comum (nao identity) para preservar o id de origem.
            if recreate:
                cur.execute("DROP TABLE IF EXISTS blogs CASCADE;")

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS blogs (
                    id     BIGINT PRIMARY KEY,
                    title  TEXT,
                    date   TEXT,
                    text   TEXT NOT NULL
                );
                """
            )

            rows = [
                (row["id"], row.get("title"), row.get("date"), row["text"])
                for row in dataset.select(range(total))
            ]

            # ON CONFLICT DO NOTHING deixa o script idempotente: rodar de novo
            # nao duplica nem falha em registros ja existentes.
            cur.executemany(
                """
                INSERT INTO blogs (id, title, date, text)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING;
                """,
                rows,
            )
        conn.commit()

        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM blogs;")
            count = cur.fetchone()[0]

    print(f"Pronto. A tabela 'blogs' agora tem {count} registro(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
