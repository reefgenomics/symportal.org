echo "Removing previous Docker Stack"
docker stack rm symportal

# Sleep for several seconds to make sure all containers are removed
sleep 15

# Deploy
export $(xargs < .env)
echo "Deploy the Symportal Stack"
docker stack deploy --compose-file docker-stack.yml symportal
echo "Done."
