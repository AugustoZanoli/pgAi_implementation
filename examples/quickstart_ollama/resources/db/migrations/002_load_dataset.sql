-- Migration substituída por um script de população para evitar ter que instalar as dependencias de python no postgres;

-- SELECT ai.load_dataset(
--     'sgoel9/sam_altman_essays', 
--     'default', 
--     table_name=>'blogs',
--     batch_size=>50,
--     max_batches=>1
-- );