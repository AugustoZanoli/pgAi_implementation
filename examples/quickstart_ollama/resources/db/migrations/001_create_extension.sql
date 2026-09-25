-- ATENCAO: o pgai NAO e mais instalado como extensao do Postgres.
--
-- No modelo antigo (pgai < 0.10) rodava-se:
--     CREATE EXTENSION IF NOT EXISTS ai CASCADE;
-- Isso nao funciona mais: a imagem timescale/timescaledb-ha nao traz o arquivo
-- de controle da extensao `ai`, e o comando falha com
-- "extension \"ai\" is not available".
--
-- Hoje o pgai e instalado como um SCHEMA (`ai`), atraves do CLI do proprio
-- vectorizer-worker, que aplica os objetos SQL no banco. Rode UMA VEZ, a partir
-- da pasta que contem o docker-compose.yml (resources/):
--
--     docker compose run --rm \
--       --entrypoint "python -m pgai install -d postgres://postgres:postgres@db:5432/pgai_ollama" \
--       vectorizer-worker
--
-- Apos rodar, o schema `ai` e suas funcoes (ex.: ai.create_vectorizer) ficam
-- disponiveis. Esta migration apenas valida que a instalacao foi feita.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'ai') THEN
        RAISE EXCEPTION
            'Schema "ai" nao encontrado. Rode o instalador do pgai antes: '
            'docker compose run --rm --entrypoint '
            '"python -m pgai install -d postgres://postgres:postgres@db:5432/pgai_ollama" '
            'vectorizer-worker';
    END IF;
END
$$;
