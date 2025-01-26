docker run -d \
    --name pensieve-pgvector \
    -p 5432:5432 \
    -e POSTGRES_PASSWORD=mysecretpassword \
    pgvector/pgvector:pg17
