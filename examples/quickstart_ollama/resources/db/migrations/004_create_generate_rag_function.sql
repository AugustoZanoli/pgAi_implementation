CREATE OR REPLACE FUNCTION generate_rag_response(query_text TEXT)
RETURNS TEXT AS $$
DECLARE
    context_chunks TEXT;
    response TEXT;
BEGIN
    SELECT string_agg(title || ': ' || chunk, ' ') INTO context_chunks
    FROM (
        SELECT title, chunk
        FROM blogs_embedding
        ORDER BY embedding <=> ai.ollama_embed('nomic-embed-text', query_text)
        LIMIT 5
    ) AS relevant_posts;

    SELECT ai.ollama_generate(
        'tinyllama',
        format('Context: %s\n\User Question: %s\b\bPlease answer the question using only the context provided. Also mention the titles of the blog posts')
    )->>'response' INTO response;

    RETURN response;
END;
$$ LANGUAGE plpgsql;