# Base image
FROM continuumio/miniconda3:23.3.1-0

# Install SSH client
RUN apt-get update && apt-get install -y openssh-client cron logrotate

# Set working directory
WORKDIR /app

# Copy environment.yml to the working directory
COPY environment.yml .
# Copy settings_blank.py to settings.py
COPY settings_blank.py settings.py
# Copy sp_config_blank.py to sp_config.py
COPY sp_config_blank.py sp_config.py

# Install Conda dependencies in the base environment
RUN conda env update -n base -f environment.yml && \
    conda init && \
    eval "$(conda shell.bash hook)"

# Install psql client
RUN apt-get update && \
    apt-get install -y postgresql-client

# Generate a secret key
RUN SECRET_KEY=$(base64 /dev/urandom | head -c50) && \
    sed -i "s|SECRET_KEY = ''|SECRET_KEY = '$SECRET_KEY'|g" settings.py

# Modify sp_config.py
RUN sed -i "s/user_name = \"undefined\"/user_name = \"bcchume\"/g" sp_config.py && \
    sed -i "s/user_email = \"undefined\"/user_email = \"bcchume@symportal.org\"/g" sp_config.py

# Copy logrotate configuration file
COPY ./cron/symportal.logrotate /etc/logrotate.d/symportal.logrotate
# Copy the rest of the application code
COPY . .

# Set environment variables
ENV PYTHONPATH=/app
ENV DJANGO_SETTINGS_MODULE=settings

# Run your application
CMD ["bash"]
