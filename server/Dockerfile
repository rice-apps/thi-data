# Use an official lightweight Python image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Prevent Python from writing .pyc files
ENV PYTHONDONTWRITEBYTECODE=1
# Ensure Python output is sent directly to the terminal without buffering
ENV PYTHONUNBUFFERED=1

# Install system dependencies (needed for some Python packages)
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev build-essential cmake \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file first (for better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . .

# (Optional) default command, though docker-compose usually overrides this
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]