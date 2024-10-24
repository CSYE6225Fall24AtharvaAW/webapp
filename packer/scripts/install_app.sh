#!/bin/bash

# Ensure the application directory exists or exit if it doesn't
mkdir -p /home/csye6225/webapp
cd /home/csye6225/webapp || exit

touch .env

# Set permissions for .env file
sudo chmod 644 /home/csye6225/webapp/.env
sudo chown csye6225:csye6225 /home/csye6225/webapp/.env

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
pip install -r requirements.txt

# Deactivate the virtual environment
deactivate
