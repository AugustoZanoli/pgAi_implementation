SELECT ai.create_vectorizer(
    'public.blogs'::regclass,

    loading => ai.loading_column(
        column_name => 'text'
    ),

    destination => ai.destination_table(
        target_table => 'blogs_embedding_storage'
    ),

    embedding => ai.embedding_ollama(
        model => 'nomic-embed-text',
        dimensions => 768
    ),

    chunking => ai.chunking_recursive_character_text_splitter(
        chunk_size => 800,
        chunk_overlap => 400
    ),

    formatting => ai.formatting_python_template(
        'Blog title: $title Publishing date: $date Blog chunk: $chunk'
    )
);