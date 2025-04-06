# Start from Ubuntu:22.04 as the base image
FROM ubuntu:22.04

# Set environment variables to avoid interactive prompts during installation
ENV DEBIAN_FRONTEND=noninteractive

# Update package lists and install Python and pip
RUN apt-get update && \
    apt-get install -y python3 python3-pip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory inside the container
WORKDIR /app

# Copy requirements file
COPY pyproject.toml .

# Install Python dependencies
RUN pip3 install flask==2.3.3 \
    flask-sqlalchemy==3.0.5 \
    gunicorn==23.0.0 \
    psycopg2-binary==2.9.7 \
    numpy==1.25.2

# Copy the rest of the application code
COPY . .

# Create necessary data directories
RUN mkdir -p data

# Expose port 8000 to the outside world
EXPOSE 8000

# Command to run the Flask application on port 8000
CMD ["python3", "start_for_docker.py"]