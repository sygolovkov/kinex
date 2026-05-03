#!/bin/bash

# Скрипт для получения Let's Encrypt сертификата в Docker

DOMAIN="kinex-pay.ru"
EMAIL="admin@kinex-pay.ru"  # Измените на вашу почту

# Создайте директории если их нет
mkdir -p ./certbot/conf
mkdir -p ./certbot/www

echo "Получаю сертификат для $DOMAIN..."

# Запустите контейнер certbot для получения сертификата
docker-compose run --rm certbot certonly \
  --webroot \
  -w /var/www/certbot \
  -d "$DOMAIN" \
  -d "www.$DOMAIN" \
  --email "$EMAIL" \
  --agree-tos \
  --no-eff-email

if [ $? -eq 0 ]; then
  echo "✓ Сертификат получен успешно!"
  echo "Перезапускаю nginx..."
  docker-compose exec -T nginx nginx -s reload
else
  echo "✗ Ошибка при получении сертификата"
  exit 1
fi
