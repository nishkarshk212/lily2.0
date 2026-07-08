#!/bin/bash
# Script to automate EC2 installation of Docker & launching the bot

# Colors for printing
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${GREEN}Installing Docker and Docker Compose...${NC}"
sudo apt-get update -y
sudo apt-get install -y docker.io docker-compose

echo -e "${GREEN}Starting and enabling Docker service...${NC}"
sudo systemctl start docker
sudo systemctl enable docker

# Check if .env file exists
if [ ! -f .env ]; then
    echo "WARNING: .env file is missing! Please configure the .env file before starting the bot."
    exit 1
fi

echo -e "${GREEN}Building and running Lily Music Bot container...${NC}"
sudo docker compose up -d --build

echo -e "${GREEN}Deployment complete! Running in background.${NC}"
echo -e "You can check logs using: ${GREEN}sudo docker logs -f lily_music_bot${NC}"
