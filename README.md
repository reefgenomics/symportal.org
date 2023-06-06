# symportal-2.0

## Get Started

### Set up `.env`

To set up environment variables, create `.env` file and put neccesary credentials and variables:

```
POSTGRES_USER=''
POSTGRES_PASSWORD=''
POSTGRES_DB=''

SYMPORTAL_DATABASE_CONTAINER=symportal-database
SYMPORTAL_FLASK_CONTAINER=symportal-flask
SYMPORTAL_NGINX_CONTAINER=symportal-nginx
SYMPORTAL_FRAMEWORK_CONTAINER=symportal-framework
```

### Build the project

To build the project with Docker Compose, run the following script

```
sudo bash run_docker.sh
```

## About

The SymPortal Framework and Flask application was written by Benjamin Hume.

The architecture migration and CI/CD set up were made by Yulia Iakovleva.
