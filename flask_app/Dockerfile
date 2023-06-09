# Base image
FROM python:3.9

# Set working directory
WORKDIR /app

# Copy requirements.txt to the working directory
COPY requirements.txt .

# Install application dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Set environment variables
ENV FLASK_APP=sp_app:app
ENV FLASK_RUN_HOST=0.0.0.0

# Expose the Flask app port
EXPOSE 5000

# Run the Flask application
CMD ["gunicorn", "sp_app:app", "-b", "0.0.0.0:5000", "--log-level", "debug", "--timeout", "240"]
