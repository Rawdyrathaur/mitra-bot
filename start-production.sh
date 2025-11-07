#!/bin/bash
set -e

echo "================================================"
echo "Mitra Bot - Production Deployment Script"
echo "================================================"
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo "ERROR: .env file not found!"
    echo "Please copy .env.example to .env and configure it:"
    echo "  cp .env.example .env"
    echo "  nano .env"
    exit 1
fi

# Check required environment variables
echo "Checking required environment variables..."
REQUIRED_VARS=(
    "POSTGRES_PASSWORD"
    "OPENAI_API_KEY"
    "JWT_SECRET_KEY"
    "SECRET_KEY"
    "ALLOWED_ORIGINS"
)

MISSING_VARS=()
for var in "${REQUIRED_VARS[@]}"; do
    if ! grep -q "^${var}=" .env || grep -q "^${var}=CHANGE" .env; then
        MISSING_VARS+=("$var")
    fi
done

if [ ${#MISSING_VARS[@]} -ne 0 ]; then
    echo "ERROR: The following required variables are not set in .env:"
    for var in "${MISSING_VARS[@]}"; do
        echo "  - $var"
    done
    echo ""
    echo "Please edit .env and set these values."
    exit 1
fi

echo "All required environment variables are set."
echo ""

# Create necessary directories
echo "Creating directories..."
mkdir -p logs uploads temp deployment/nginx/conf.d deployment/nginx/ssl

# Build and start services
echo "Starting Mitra Bot with Docker Compose..."
docker-compose -f docker-compose.prod.yml up -d --build

echo ""
echo "Waiting for services to be healthy..."
sleep 10

# Check health
echo "Checking application health..."
HEALTH_CHECK=$(curl -s http://localhost:5000/api/health || echo "failed")

if echo "$HEALTH_CHECK" | grep -q "healthy"; then
    echo ""
    echo "================================================"
    echo "SUCCESS! Mitra Bot is running!"
    echo "================================================"
    echo ""
    echo "Access the API at: http://localhost:5000"
    echo "Health check: http://localhost:5000/api/health"
    echo ""
    echo "View logs with:"
    echo "  docker-compose -f docker-compose.prod.yml logs -f mitra-bot"
    echo ""
    echo "Stop services with:"
    echo "  docker-compose -f docker-compose.prod.yml down"
    echo ""
else
    echo ""
    echo "WARNING: Application may not be fully ready yet."
    echo "Check logs with:"
    echo "  docker-compose -f docker-compose.prod.yml logs mitra-bot"
    echo ""
    exit 1
fi
