#!/bin/bash
set -e

# This script runs during PostgreSQL container initialization
# It ensures the database and user are properly set up

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Create extensions if needed
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

EOSQL

echo "Database initialization completed successfully"