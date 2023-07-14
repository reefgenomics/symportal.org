# Remove previous builds
docker stack rm symportal

# Sleep for several seconds to make sure all containers are removed
sleep 15

# Deploy
export $(xargs < .env)
docker stack deploy --compose-file docker-stack.yml symportal
