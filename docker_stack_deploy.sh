echo "Removing previous Docker Stack"
docker stack rm symportal

# Sleep for several seconds to make sure all containers are removed
echo "Sleep for several seconds..."
sleep 20

# Deploy
export $(xargs < .env)
echo "Deploy the Symportal Stack"
docker stack deploy --compose-file docker-stack.yml symportal

# Get the container ID
CONTAINER_ID=$(docker ps --filter "name=database" --format "{{.ID}}")

# Copy the SQL dump file into the container
docker cp ./database/postgres_dump_after.sql $CONTAINER_ID:/tmp/postgres_dump_after.sql

echo "Drop existing database schema"
docker exec -it $CONTAINER_ID \
    psql -U postgres \
     -c "DROP SCHEMA public CASCADE; \
         CREATE SCHEMA public; \
         GRANT ALL ON SCHEMA public TO postgres; \
         GRANT ALL ON SCHEMA public TO public; \
         DROP DATABASE postgres;"

# Execute the psql command inside the container
echo "Resotore the dump file"
docker exec -it $CONTAINER_ID psql -U postgres -d postgres -f /tmp/postgres_dump_after.sql

echo "Set up cron jobs"
containers="flask-app symportal-framework"
for container in $containers; do
    CONTAINER_ID=$(docker ps --filter "name=${container}" --format "{{.ID}}")
    echo $container: $CONTAINER_ID
    docker exec -it $CONTAINER_ID bash -c "
       env >> /etc/environment && \
       service cron start && \
       crontab /app/cron/crontab"
done

echo "Done."
