# Use a Python 3.11 base image for Google Cloud Functions/Run compatibility
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt requirements.txt

# Install dependencies (Flask, firebase-admin, etc.)
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . /app

# Expose the port that Flask will run on (Cloud Run defaults to 8080)
ENV PORT 8080

# Command to run the Flask application
# The default host must be set to 0.0.0.0 for Cloud Run to route traffic correctly
CMD ["python3", "app.py"]
