#!/bin/bash
set -e

DOMAIN="kinex-pay.ru"
EMAIL="admin@kinex-pay.ru"

# Detect docker compose command
if docker compose version > /dev/null 2>&1; then
    DC="docker compose"
elif command -v docker-compose > /dev/null 2>&1; then
    DC="docker-compose"
else
    echo "Error: neither 'docker compose' nor 'docker-compose' found"
    exit 1
fi

echo "Using: $DC"

mkdir -p ./certbot/conf/live/$DOMAIN
mkdir -p ./certbot/www

# Step 1: dummy self-signed cert so Nginx can start
echo "Creating dummy certificate..."
openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
    -keyout "./certbot/conf/live/$DOMAIN/privkey.pem" \
    -out  "./certbot/conf/live/$DOMAIN/fullchain.pem" \
    -subj "/CN=localhost"

# Step 2: start Nginx with dummy cert
echo "Starting Nginx..."
$DC up --detach nginx
sleep 5

# Step 3: remove dummy cert
echo "Removing dummy certificate..."
rm -rf "./certbot/conf/live/$DOMAIN" \
       "./certbot/conf/archive/$DOMAIN" \
       "./certbot/conf/renewal/$DOMAIN.conf"

# Step 4: get real cert
echo "Requesting Let's Encrypt certificate for $DOMAIN..."
docker run --rm \
    -v "$(pwd)/certbot/conf:/etc/letsencrypt" \
    -v "$(pwd)/certbot/www:/var/www/certbot" \
    certbot/certbot:latest certonly \
    --webroot \
    -w /var/www/certbot \
    -d "$DOMAIN" \
    -d "www.$DOMAIN" \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    --force-renewal

echo "Reloading Nginx with real certificate..."
$DC exec -T nginx nginx -s reload

echo "Starting remaining services..."
$DC up --detach

echo "Done!"
