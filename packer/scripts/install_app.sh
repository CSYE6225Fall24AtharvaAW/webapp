#!/bin/bash

# Ensure the application directory exists or exit if it doesn't
mkdir -p /home/ubuntu/webapp
cd /home/ubuntu/webapp || exit

# Create a .env file with database connection details using environment variables
cat <<EOT > .env
DATABASE_URL="postgresql+asyncpg://$DB_USERNAME:$DB_PASSWORD@$DB_HOST:$DB_PORT/$DB_NAME"
EOT

# Ensure the .env file is created with the correct permissions
sudo chmod 644 /home/ubuntu/webapp/.env
sudo chown ubuntu:ubuntu /home/ubuntu/webapp/.env

# Install Python3 virtual environment tools
sudo apt-get update
sudo apt-get install -y python3-venv

# Create a virtual environment named 'venv'
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Update pip to its latest version
pip install --upgrade pip

# Install FastAPI, Uvicorn and other dependencies from requirements.txt
pip install fastapi uvicorn
pip install -r requirements.txt

# Deactivate the virtual environment
deactivate
