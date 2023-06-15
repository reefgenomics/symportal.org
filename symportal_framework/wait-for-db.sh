#!/bin/bash

# Wait until the database container is ready
until PGPASSWORD=$POSTGRES_PASSWORD psql -h $SYMPORTAL_DATABASE_CONTAINER -U $POSTGRES_USER -c '\q'; do
    echo "Waiting for the database container to be ready..."
    sleep 1
done

echo "Database is ready"

# Run migrations and populate the database
python manage.py migrate && \
python populate_db_ref_seqs.py

