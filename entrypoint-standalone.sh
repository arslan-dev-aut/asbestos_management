#!/bin/sh
set -e

# Schema is managed in Azure (tables pre-created by hand-run SQL files under
# backend/database/migrations/); no migration step at boot.

# Resolve DNS nameserver for nginx resolver directive
export NGINX_RESOLVER=$(awk 'BEGIN{ORS=" "} $1=="nameserver" {print $2; exit}' /etc/resolv.conf)
# In standalone mode, backend is on localhost
export BACKEND_UPSTREAM=http://127.0.0.1:8000

# Render the nginx config template
envsubst '${NGINX_RESOLVER} ${BACKEND_UPSTREAM}' \
  < /etc/nginx/conf.d/default.conf.template \
  > /etc/nginx/conf.d/default.conf

# Replace placeholders with environment variables in frontend JS files
echo "Replacing environment variables in JS files..."
for file in $(find /usr/share/nginx/html -type f -name "*.js"); do
  sed -i "s|VITE_BASE_GATEWAY_PLACEHOLDER|${VITE_BASE_GATEWAY}|g" $file
  sed -i "s|VITE_BASE_CLIENT_ID_PLACEHOLDER|${VITE_BASE_CLIENT_ID}|g" $file
  sed -i "s|VITE_BASE_IDENTITY_PLACEHOLDER|${VITE_BASE_IDENTITY}|g" $file
  sed -i "s|VITE_API_URL_PLACEHOLDER|${VITE_API_URL}|g" $file
  sed -i "s|VITE_API_BASE_URL_PLACEHOLDER|${VITE_API_BASE_URL}|g" $file
done
echo "Replacing environment variables in JS files done"

exec supervisord -c /etc/supervisord.conf