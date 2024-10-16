#!/bin/bash
# Place the FastAPI systemd service file and enable it

# Copy the systemd service file to the correct location
sudo cp /tmp/webapp.service /etc/systemd/system/webapp.service

# Reload systemd to recognize the new service
sudo systemctl daemon-reload

# Ensure the service file has the correct permissions
sudo chmod 644 /etc/systemd/system/webapp.service

# Enable the service to start on boot
sudo systemctl enable webapp.service

# Start the FastAPI web service
sudo systemctl start webapp.service
