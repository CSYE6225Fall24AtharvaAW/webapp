#!/bin/bash
# Create PostgreSQL user and database
sudo -u postgres psql -c "CREATE USER fastapi_user WITH PASSWORD 'password';"
sudo -u postgres psql -c "CREATE DATABASE fastapi_db OWNER fastapi_user;"
sudo systemctl enable postgresql
sudo systemctl start postgresql
