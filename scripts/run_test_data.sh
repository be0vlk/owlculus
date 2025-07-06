#!/bin/bash
# Script to run the test data creation inside the Docker container

echo "Running test data creation script inside Docker container..."

# Copy the script to the container and run it from the correct directory
docker compose -f docker-compose.dev.yml cp scripts/create_test_data.py backend:/tmp/create_test_data.py
docker compose -f docker-compose.dev.yml exec -w /app backend python3 /tmp/create_test_data.py

echo "Test data script execution completed!"