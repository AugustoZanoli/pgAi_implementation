-- Cria o vectorizer da tabela `blogs` usando o Ollama.
--
-- O pgai gera embeddings automaticamente a partir da coluna `text`. Com o
-- destino em tabela (o padrao), o pgai cria DOIS objetos:
--   * a tabela de armazenamento `blogs_embedding_store` (embedding_uuid, id,
--     chunk_seq, chunk, embedding) -- NAO tem as colunas de origem;
--   * a VIEW `blogs_embedding`, que junta a tabela de origem `blogs` com os
--     embeddings e, portanto, expoe TODAS as colunas de `blogs`
--     (id, title, date, text) + chunk, embedding, chunk_seq, embedding_uuid.
--
-- O leitor (src/main.py) consulta a VIEW `blogs_embedding` porque precisa do
-- title/date/id de origem junto de cada chunk.
--
-- O worker (servico `vectorizer-worker` do docker-compose) processa os chunks
-- chamando o Ollama em OLLAMA_HOST.
--
-- IMPORTANTE: o mesmo modelo e o mesmo numero de dimensoes precisam ser usados
-- na indexacao (aqui) e na consulta (ai.ollama_embed no leitor), senao a
-- comparacao de vetores com o operador <=> fica invalida.
--
-- Pre-requisito: o modelo de embedding precisa estar disponivel no Ollama.
--   docker compose exec ollama ollama pull nomic-embed-text

SELECT ai.create_vectorizer(
    'blogs'::regclass,
    loading     => ai.loading_column(column_name => 'text'),
    embedding   => ai.embedding_ollama('nomic-embed-text', 768),
    destination => ai.destination_table(
        target_table => 'blogs_embedding_store',
        view_name    => 'blogs_embedding'
    ),
    if_not_exists => true
);
