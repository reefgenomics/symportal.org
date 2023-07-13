# SymPortal-2.0

## Get Started

### Set up `.env`

To set up environment variables, create `.env` file and put neccesary credentials and variables:

```
CONTACT_EMAIL_ADDRESS='yulia.iakovleva@uni-konstanz.de'
GOOGLE_MAPS_API_KEY=''
POSTGRES_USER=''
POSTGRES_PASSWORD=''
POSTGRES_DB=''
SFTP_UID=1001
SFTP_GID=1001
SFTP_USERNAME=''
SFTP_PASSWORD=''
SFTP_HOME=''
SYMPORTAL_DATABASE_CONTAINER=symportal-database
SYMPORTAL_FLASK_CONTAINER=symportal-flask
SYMPORTAL_NGINX_CONTAINER=symportal-nginx
SYMPORTAL_FRAMEWORK_CONTAINER=symportal-framework
```

### Build the project

To build the project with Docker Swarm, you have to initialize it in Manager (zygote) node:

```commandline
docker swarm init
```

Then follow the instruction form the provided output to add the worker node.

To deploy the project run the following script:

```commandline
bash deploy_docker_swarm.sh
```

## Application Architecture

This project utilizes the "Infrastructure as Code" approach to set up a scalable and reproducible architecture.

It utilizes Docker Compose to manage four containers:

* NGINX
* Flask + Gunicorn
* Symportal Framework
* PostgreSQL Database
* SFTP Server

Here below is an overview of the application architecture schema.

![image](https://github.com/greenjune-ship-it/symportal-2.0/assets/83506881/9a0b14e8-6acc-470f-863b-b814173fa5e9)

Our Docker registry at Docker Hub: https://hub.docker.com/r/greenjune/symportal-kitchen/tags.

## About

The SymPortal Framework and Flask application was written by Benjamin Hume [benjamincchume@gmail.com](benjamincchume@gmail.com).

The architecture migration and CI/CD set up were made by Yulia Iakovleva [yulia.iakovleva@uni-konstanz.de](yulia.iakovleva@uni-konstanz.de).
