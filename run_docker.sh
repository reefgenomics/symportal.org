#!/bin/bash

echo "Killing old docker processes"
docker compose rm -fs

echo "Building docker containers"
docker compose up --build -d --remove-orphans

echo "Set up cron jobs"
docker compose exec flask-app bash -c "env >> /etc/environment && service cron start && crontab /app/cron/crontab"

# Pause everything except the database service
docker compose pause nginx flask-app symportal-framework

echo "Drop the database and restore from backup"
docker compose exec database \
    psql -U postgres \
     -c "DROP SCHEMA public CASCADE; \
         CREATE SCHEMA public; \
         GRANT ALL ON SCHEMA public TO postgres; \
         GRANT ALL ON SCHEMA public TO public; \
         DROP DATABASE postgres;"

docker compose exec -T database psql -U postgres -d postgres < ./database/postgres_dump_after.sql
echo "Done!"

docker compose unpause nginx flask-app symportal-framework
