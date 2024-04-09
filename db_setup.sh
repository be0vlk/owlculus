#!/bin/bash

# Check if PostgreSQL is installed by checking if the psql command exists
if ! which psql > /dev/null 2>&1; then
  echo "PostgreSQL is not installed. Attempting to install.."
  sudo apt update && sudo apt install postgresql -qq -y
fi

# Check if PostgreSQL service is running
if ! service postgresql status > /dev/null 2>&1; then
  echo "PostgreSQL service is not running. Trying to start it..."
  sudo service postgresql start
  # Verify if the service successfully started
  if ! service postgresql status > /dev/null 2>&1; then
    echo "Failed to start PostgreSQL service. Please start it manually and try again."
    exit 1
  fi
fi

# Load the .env file
set -o allexport
source .env
set +o allexport

# Function to check if a PostgreSQL user (role) exists
check_user_exists() {
  username=$1
  exists=$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$username'" 2>&1 | grep -v "could not change directory to" >&2)
  echo "$exists"
}

# Function to create a PostgreSQL user (role)
create_user() {
  username=$1
  password=$2
  sudo -u postgres psql -c "CREATE USER $username WITH PASSWORD '$password';" 2>&1 | grep -v "could not change directory to" >&2
}

# Function to check if a PostgreSQL database exists
check_database_exists() {
  dbname=$1
  exists=$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$dbname'" 2>&1 | grep -v "could not change directory to" >&2)
  echo "$exists"
}

# Function to create a PostgreSQL database
create_database() {
  dbname=$1
  owner=$2
  sudo -u postgres psql -c "CREATE DATABASE $dbname OWNER $owner;" 2>&1 | grep -v "could not change directory to" >&2
}

# Function to grant privileges to a user on a database
grant_privileges() {
  dbname=$1
  username=$2
  sudo -u postgres psql -d "$dbname" -c "GRANT ALL PRIVILEGES ON DATABASE $dbname TO $username;" 2>&1 | grep -v "could not change directory to" >&2
  sudo -u postgres psql -d "$dbname" -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $username;" 2>&1 | grep -v "could not change directory to" >&2
  sudo -u postgres psql -d "$dbname" -c "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $username;" 2>&1 | grep -v "could not change directory to" >&2
  sudo -u postgres psql -d "$dbname" -c "GRANT USAGE, CREATE ON SCHEMA public TO $username;" 2>&1 | grep -v "could not change directory to" >&2
}


# Use the DATABASE_URI from the .env file
uri=$DATABASE_URI

# Use parameter expansion to extract URI components
username=$(echo $uri | sed -e 's/postgresql:\/\///' -e 's/:.*//')
password=$(echo $uri | sed -e 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/' | sed -e 's/\([^:]*\):.*/\1/')
dbname=$(echo $uri | sed -e 's/.*@.*\///')
echo "Username to be processed: $username"
echo "Database to be processed: $dbname"


# Check if user exists and create if not
if [ -z "$(check_user_exists $username)" ]; then
  echo "Creating user: $username"
  create_user $username $password
else
  echo "User $username already exists, skipping creation."
fi

# Check if database exists and create if not
if [ -z "$(check_database_exists $dbname)" ]; then
  echo "Creating database: $dbname"
  create_database $dbname $username
else
  echo "Database $dbname already exists, skipping creation."
fi

# Grant privileges to the user on the database
echo "Granting privileges to $username on $dbname"
grant_privileges $dbname $username

echo "Setup complete."
