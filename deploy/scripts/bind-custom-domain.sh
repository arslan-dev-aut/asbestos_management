#!/usr/bin/env bash
set -euo pipefail

require() {
  local name="$1"
  if [ -z "${!name:-}" ]; then
    echo "Missing required environment variable: ${name}" >&2
    exit 1
  fi
}

require RESOURCEGROUP
require CONTAINERNAME
require CONTAINERWEBAPPENVIRONMENTNAME
require CONTAINERAUTENVIRONMENTNAME
require CUSTOM_HOSTNAME
require CERTIFICATENAME
require CF_API_TOKEN
require CF_ZONE_ID

CUSTOM_HOSTNAME_LC="$(echo "${CUSTOM_HOSTNAME}" | tr '[:upper:]' '[:lower:]')"
if [ -z "${CUSTOM_HOSTNAME_LC}" ]; then
  echo "CUSTOM_HOSTNAME resolved to an empty value." >&2
  exit 1
fi

CONFIG_FILE="${CONFIG_FILE:-${BUILD_SOURCESDIRECTORY}/deploy/config.json}"
APP_TYPE="$(jq -r '.app_type // ""' "$CONFIG_FILE")"
if [ -n "${APP_TYPE}" ] && ! echo "${APP_TYPE}" | grep -Eq '^(WebApp|AUT)$'; then
  echo "Invalid app_type in config.json: '${APP_TYPE}' (expected 'WebApp' or 'AUT')" >&2
  exit 1
fi

if [ "$APP_TYPE" = "AUT" ]; then
  CONTAINERENVIRONMENTNAME="$CONTAINERAUTENVIRONMENTNAME"
  INFRASTRUCTURESUBNETRESOURCEID="${AUTOMATIONSUBNETRESOURCEID:-}"
  echo "Selected AUT environment: $CONTAINERENVIRONMENTNAME"
elif [ "$APP_TYPE" = "WebApp" ]; then
  CONTAINERENVIRONMENTNAME="$CONTAINERWEBAPPENVIRONMENTNAME"
  INFRASTRUCTURESUBNETRESOURCEID="${WEBAPPSUBNETRESOURCEID:-}"
  echo "Selected WebApp environment: $CONTAINERENVIRONMENTNAME"
else
  echo "Unexpected APP_TYPE value: '$APP_TYPE'. Expected 'WebApp' or 'AUT'" >&2
  exit 1
fi


# Cloudflare DNS upserts require jq + curl.
if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required for Cloudflare DNS updates." >&2
  exit 1
fi
if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required for Cloudflare DNS updates." >&2
  exit 1
fi

cf_api() {
  local method="$1"
  local path="$2"
  local data="${3:-}"
  local url="https://api.cloudflare.com/client/v4${path}"
  local args=(
    -sS
    -X "${method}"
    "${url}"
    -H "Authorization: Bearer ${CF_API_TOKEN}"
    -H "Content-Type: application/json"
    -w "\n__HTTP_STATUS:%{http_code}\n"
  )
  if [ -n "${data}" ]; then
    args+=(--data "${data}")
  fi

  local resp http_status body
  resp="$(curl "${args[@]}")"
  http_status="$(echo "${resp}" | awk -F: '/^__HTTP_STATUS:/ {print $2}' | tail -n1 | tr -d '\r')"
  body="$(echo "${resp}" | sed '/^__HTTP_STATUS:/d')"

  if [ -z "${http_status:-}" ] || [ "${http_status}" -lt 200 ] || [ "${http_status}" -ge 300 ]; then
    echo "Cloudflare API error: ${method} ${path} (HTTP ${http_status:-unknown})" >&2
    echo "${body}" >&2
    return 1
  fi

  echo "${body}"
}

cf_upsert_record() {
  local type="$1"
  local name="$2"
  local content="$3"
  local proxied="${4:-false}"

  if [ "${type}" = "TXT" ]; then
    # Cloudflare API expects TXT content wrapped in quotes.
    if [[ "${content}" != \"*\" ]]; then
      content="\"${content}\""
    fi
  fi

  local list
  list="$(cf_api GET "/zones/${CF_ZONE_ID}/dns_records?type=${type}&name=${name}")"
  local existing_id
  existing_id="$(echo "${list}" | jq -r '.result[0].id // empty')"

  local payload
  payload="$(jq -n --arg type "${type}" --arg name "${name}" --arg content "${content}" --argjson proxied "${proxied}" \
    '{type:$type,name:$name,content:$content,ttl:1,proxied:$proxied}')"

  if [ -n "${existing_id:-}" ]; then
    echo "Updating Cloudflare ${type} record: ${name}"
    cf_api PUT "/zones/${CF_ZONE_ID}/dns_records/${existing_id}" "${payload}" >/dev/null
  else
    echo "Creating Cloudflare ${type} record: ${name}"
    cf_api POST "/zones/${CF_ZONE_ID}/dns_records" "${payload}" >/dev/null
  fi
}

echo "Fetching Container App FQDN + customDomainVerificationId..."
FQDN="$(az containerapp show -n "${CONTAINERNAME}" -g "${RESOURCEGROUP}" -o tsv --query "properties.configuration.ingress.fqdn")"
VERIFICATION_ID="$(az containerapp show -n "${CONTAINERNAME}" -g "${RESOURCEGROUP}" -o tsv --query "properties.customDomainVerificationId")"

ZONE_NAME="$(cf_api GET "/zones/${CF_ZONE_ID}" | jq -r '.result.name // empty')"
if [ -z "${ZONE_NAME:-}" ]; then
  echo "Could not resolve Cloudflare zone name for zone id '${CF_ZONE_ID}'." >&2
  exit 1
fi

DNS_RECORD_NAME="${CUSTOM_HOSTNAME_LC}"
if [ "${DNS_RECORD_NAME}" = "@" ]; then
  DNS_RECORD_FQDN="${ZONE_NAME}"
elif echo "${DNS_RECORD_NAME}" | grep -q '\.'; then
  DNS_RECORD_FQDN="${DNS_RECORD_NAME}"
else
  DNS_RECORD_FQDN="${DNS_RECORD_NAME}.${ZONE_NAME}"
fi

if ! echo "${DNS_RECORD_FQDN}" | grep -Eq "(.+)\\.${ZONE_NAME}$|^${ZONE_NAME}$"; then
  echo "CUSTOM_HOSTNAME ('${CUSTOM_HOSTNAME}') must be within the Cloudflare zone '${ZONE_NAME}'." >&2
  exit 1
fi

if [ -z "${FQDN:-}" ] || [ "${FQDN}" = "null" ]; then
  echo "Could not resolve Container App FQDN for ${CONTAINERNAME}." >&2
  exit 1
fi
if [ -z "${VERIFICATION_ID:-}" ] || [ "${VERIFICATION_ID}" = "null" ]; then
  echo "Could not resolve customDomainVerificationId for ${CONTAINERNAME}." >&2
  exit 1
fi

# ============================================
# Check if hostname is already bound
# ============================================
echo "Checking if hostname '${DNS_RECORD_FQDN}' is already bound..."
EXISTING_HOSTNAMES=$(az containerapp show -n "${CONTAINERNAME}" -g "${RESOURCEGROUP}" \
  --query "properties.configuration.ingress.customDomains[].name" -o tsv 2>/dev/null || true)

if echo "${EXISTING_HOSTNAMES}" | grep -qFx "${DNS_RECORD_FQDN}"; then
  echo "✅ Hostname '${DNS_RECORD_FQDN}' is already bound to '${CONTAINERNAME}'. Skipping bind."
  exit 0
fi

echo "Hostname not yet bound. Proceeding with DNS setup and binding..."

# ============================================
# Ensure Cloudflare DNS records
# ============================================
echo "Ensuring Cloudflare CNAME: ${DNS_RECORD_FQDN} -> ${FQDN}"
cf_upsert_record "CNAME" "${DNS_RECORD_FQDN}" "${FQDN}" false

echo "Ensuring Cloudflare TXT: asuid.${DNS_RECORD_FQDN} = ${VERIFICATION_ID}"
cf_upsert_record "TXT" "asuid.${DNS_RECORD_FQDN}" "${VERIFICATION_ID}" false

# ============================================
# Smart DNS propagation wait with polling
# ============================================
echo "Waiting for DNS propagation..."
MAX_DNS_WAIT=180  # Maximum wait time in seconds
DNS_CHECK_INTERVAL=10
DNS_ELAPSED=0
DNS_READY=false

while [ $DNS_ELAPSED -lt $MAX_DNS_WAIT ]; do
  # Check CNAME resolution
  RESOLVED_CNAME=$(dig +short CNAME "${DNS_RECORD_FQDN}" 2>/dev/null | head -1 | sed 's/\.$//' || true)
  # Check TXT record
  RESOLVED_TXT=$(dig +short TXT "asuid.${DNS_RECORD_FQDN}" 2>/dev/null | tr -d '"' || true)
  
  if [ -n "${RESOLVED_CNAME}" ] && [ -n "${RESOLVED_TXT}" ]; then
    echo "✅ DNS propagated! CNAME: ${RESOLVED_CNAME}, TXT: (verified)"
    DNS_READY=true
    break
  fi
  
  echo "  Waiting for DNS... (${DNS_ELAPSED}s / ${MAX_DNS_WAIT}s) CNAME: ${RESOLVED_CNAME:-<pending>}"
  sleep $DNS_CHECK_INTERVAL
  DNS_ELAPSED=$((DNS_ELAPSED + DNS_CHECK_INTERVAL))
done

if [ "$DNS_READY" = false ]; then
  echo "⚠️ DNS propagation timeout after ${MAX_DNS_WAIT}s. Proceeding anyway (Azure may still succeed)..."
fi

# ============================================
# Bind hostname with retry logic
# ============================================
echo "Binding hostname + certificate in Container Apps..."
echo "Binding hostname: ${DNS_RECORD_FQDN}"
echo "Using certificate: ${CERTIFICATENAME}"

MAX_BIND_RETRIES=5
BIND_RETRY_DELAY=30
BIND_SUCCESS=false

for attempt in $(seq 1 $MAX_BIND_RETRIES); do
  echo "=== Hostname bind attempt $attempt of $MAX_BIND_RETRIES ==="
  
  if az containerapp hostname bind \
    -n "${CONTAINERNAME}" \
    -g "${RESOURCEGROUP}" \
    -e "${CONTAINERENVIRONMENTNAME}" \
    --certificate "${CERTIFICATENAME}" \
    --hostname "${DNS_RECORD_FQDN}" \
    -v cname 2>&1; then
    BIND_SUCCESS=true
    break
  else
    BIND_EXIT_CODE=$?
    if [ $attempt -lt $MAX_BIND_RETRIES ]; then
      echo "⚠️ Hostname bind failed (exit code: $BIND_EXIT_CODE). DNS may not be propagated yet."
      echo "   Retrying in ${BIND_RETRY_DELAY}s..."
      sleep $BIND_RETRY_DELAY
    fi
  fi
done

if [ "$BIND_SUCCESS" = false ]; then
  echo "❌ Hostname bind failed after $MAX_BIND_RETRIES attempts"
  echo "   Please verify:"
  echo "   1. DNS records are correctly configured"
  echo "   2. Certificate '${CERTIFICATENAME}' exists in environment '${CONTAINERENVIRONMENTNAME}'"
  echo "   3. The hostname is not already bound to another app"
  exit 1
fi

echo "✅ Done. Custom domain '${DNS_RECORD_FQDN}' is now bound to '${CONTAINERNAME}'."
