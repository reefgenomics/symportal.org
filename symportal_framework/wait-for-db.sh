#!/bin/bash

# Wait until the database container is ready
until docker compose exec -T $SYMPORTAL_DATABASE_CONTAINER psql -h $SYMPORTAL_DATABASE_CONTAINER -U $POSTGRES_USER -c '\q'; do
    echo "Waiting for the database container to be ready..."
    sleep 1
done

# Start the application container
docker compose up -d $SYMPORTAL_DATABASE_CONTAINER
