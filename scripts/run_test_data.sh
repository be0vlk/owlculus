#!/bin/bash
# Script to run the test data creation inside the Docker container

echo "Running test data creation script inside Docker container..."

# Copy the script to the container and run it from the correct directory
DEV_COMPOSE=(./scripts/compose.sh development)
"${DEV_COMPOSE[@]}" cp scripts/create_test_data.py backend:/tmp/create_test_data.py
"${DEV_COMPOSE[@]}" exec -w /app backend python3 /tmp/create_test_data.py

echo "Test data script execution completed!"
