docker run -d \
    --name pensieve-pgvector \
    -p 5432:5432 \
    -e POSTGRES_PASSWORD=mysecretpassword \
    -v pensieve-pgdata:/var/lib/postgresql/data \
    pgvector/pgvector:pg17
