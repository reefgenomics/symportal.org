# Base image
FROM python:3.9

# Install SSH client
RUN apt-get update && apt-get install -y openssh-client cron logrotate

# Set working directory
WORKDIR /app

# Copy requirements.txt to the working directory
COPY requirements.txt .

# Install application dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy logrotate configuration file
COPY ./cron/symportal.logrotate /etc/logrotate.d/symportal.logrotate
# Copy the rest of the application code
COPY . .

# Set environment variables
ENV FLASK_APP=sp_app:app
ENV FLASK_RUN_HOST=0.0.0.0
ENV PYTHONPATH=/app

# Expose the Flask app port
EXPOSE 5000

# Set up proper permissions for logrotate configuration file
RUN chmod 0644 /etc/logrotate.d/symportal.logrotate

# Run the Flask application
CMD ["gunicorn", "sp_app:app", "-b", "0.0.0.0:5000", "--log-level", "debug", "--timeout", "240"]
