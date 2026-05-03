#!/bin/bash

DOMAIN="kinex-pay.ru"
EMAIL="admin@kinex-pay.ru"

mkdir -p ./certbot/conf/live/$DOMAIN
mkdir -p ./certbot/www

# Step 1: create a dummy self-signed cert so Nginx can start
if [ ! -f "./certbot/conf/live/$DOMAIN/fullchain.pem" ]; then
    echo "Creating dummy certificate..."
    docker compose run --rm --entrypoint "\
        openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
        -keyout /etc/letsencrypt/live/$DOMAIN/privkey.pem \
        -out /etc/letsencrypt/live/$DOMAIN/fullchain.pem \
        -subj '/CN=localhost'" certbot
fi

# Step 2: start Nginx (it can now start with the dummy cert)
echo "Starting Nginx..."
docker compose up -d nginx

sleep 3

# Step 3: delete dummy cert and get a real one
echo "Removing dummy certificate..."
docker compose run --rm --entrypoint "\
    rm -rf /etc/letsencrypt/live/$DOMAIN \
           /etc/letsencrypt/archive/$DOMAIN \
           /etc/letsencrypt/renewal/$DOMAIN.conf" certbot

echo "Requesting Let's Encrypt certificate for $DOMAIN..."
docker compose run --rm certbot certonly \
    --webroot \
    -w /var/www/certbot \
    -d "$DOMAIN" \
    -d "www.$DOMAIN" \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    --force-renewal

if [ $? -eq 0 ]; then
    echo "Certificate obtained successfully!"
    docker compose exec nginx nginx -s reload
    echo "Done. Starting remaining services..."
    docker compose up -d
else
    echo "Failed to obtain certificate"
    exit 1
fi
