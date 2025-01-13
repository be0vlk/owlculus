#!/bin/bash

CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}---- Starting Owlculus setup ----${NC}"
read -p "Have you read the README? (yes/no) " answer
if [[ "$answer" != "yes" ]]; then
    echo -e "${RED}Please read the README file before proceeding.${NC}"
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    cp .env.example .env
fi

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo -e "${YELLOW}PostgreSQL is not installed. Installing PostgreSQL...${NC}"
    sudo apt-get update
    sudo apt-get install -qq -y postgresql
    sudo service postgresql start
else
    echo -e "${CYAN}PostgreSQL is already installed${NC}"
    sudo service postgresql start
fi

# Check if npm is installed
if ! command -v npm &> /dev/null; then
    echo -e "${YELLOW}npm is not installed. Installing npm...${NC}"
    sudo apt-get update
    sudo apt-get install -qq -y npm
else
    echo -e "${CYAN}npm is already installed${NC}"
fi

# Create Python virtual environment
echo -e "${CYAN}Setting up Python virtual environment...${NC}"
python3 -m venv venv

# Activate virtual environment
echo -e "${CYAN}Activating virtual environment...${NC}"
source venv/bin/activate

# Install required packages
echo -e "${CYAN}Installing Python dependencies...${NC}"
pip3 install -r requirements.txt --quiet

# Deactivate virtual environment
deactivate

# Generate a random secret key
NEW_SECRET_KEY=$(openssl rand -hex 32)

# Replace or add the SECRET_KEY in the .env file
echo -e "${CYAN}Updating secret key in .env...${NC}"
if grep -q "^SECRET_KEY=" .env; then
    sed -i "s/^SECRET_KEY=.*/SECRET_KEY=$NEW_SECRET_KEY/" .env
else
    echo "SECRET_KEY=$NEW_SECRET_KEY" >> .env
fi

# Install the npm dependencies
echo -e "${CYAN}Installing npm dependencies...${NC}"
cd frontend && npm install --quiet && cd ..

echo -e "${CYAN}---- Setup complete! ----${NC}"