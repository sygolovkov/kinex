#!/bin/bash
set -e

DOMAIN="kinex-pay.ru"
EMAIL="admin@kinex-pay.ru"

mkdir -p ./certbot/conf/live/$DOMAIN
mkdir -p ./certbot/www

# Step 1: dummy self-signed cert so Nginx can start before the real cert exists
echo "Creating dummy certificate..."
openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
    -keyout "./certbot/conf/live/$DOMAIN/privkey.pem" \
    -out  "./certbot/conf/live/$DOMAIN/fullchain.pem" \
    -subj "/CN=localhost"

# Step 2: start Nginx (can now start with dummy cert)
echo "Starting Nginx..."
docker compose up -d nginx
sleep 5

# Step 3: remove dummy cert
echo "Removing dummy certificate..."
rm -rf "./certbot/conf/live/$DOMAIN" \
       "./certbot/conf/archive/$DOMAIN" \
       "./certbot/conf/renewal/$DOMAIN.conf"

# Step 4: get real cert via plain docker run (no compose run quirks)
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
docker compose exec nginx nginx -s reload

echo "Starting remaining services..."
docker compose up -d

echo "Done!"
