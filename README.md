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

To build the project with Docker Compose, run the following script

```
sudo bash run_docker.sh
```

## Application Architecture

This project utilizes the "Infrastructure as Code" approach to set up a scalable and reproducible architecture.

It utilizes Docker Compose to manage four containers:

* NGINX
* Flask + Gunicorn
* Symportal Framework
* PostgreSQL Database

Here below is an overview of the application architecture schema.

![image](https://github.com/greenjune-ship-it/symportal-2.0/assets/83506881/fcbf98a6-37e5-4d07-8940-e39f6b96cacc)

## About

The SymPortal Framework and Flask application was written by Benjamin Hume [benjamincchume@gmail.com](benjamincchume@gmail.com).

The architecture migration and CI/CD set up were made by Yulia Iakovleva [yulia.iakovleva@uni-konstanz.de](yulia.iakovleva@uni-konstanz.de).
