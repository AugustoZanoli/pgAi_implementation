CREATE TABLE IF NOT EXISTS wiki (
    id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    text TEXT NOT NULL
);


SELECT ai.create_vectorizer(
     'wiki'::regclass,
     loading => ai.loading_column(column_name => 'text'),
     destination => ai.destination_table(target_table => 'wiki_embedding_storage'),
     embedding => ai.embedding_litellm(
         'gemini/gemini-embedding-001',
         768,
         api_key_name => 'GOOGLE_API_KEY'
     )
);
