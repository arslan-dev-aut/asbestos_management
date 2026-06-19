#!/usr/bin/env bash
set -euo pipefail

require() {
  local name="$1"
  if [ -z "${!name:-}" ]; then
    echo "Missing required environment variable: ${name}" >&2
    exit 1
  fi
}

require BUILD_SOURCESDIRECTORY
require BUILD_BUILDID
require RESOURCEGROUP
require REGION
require CONTAINERWEBAPPENVIRONMENTNAME
require CONTAINERAUTENVIRONMENTNAME
require CONTAINERNAME
require AZURECONTAINERREGISTRY
require USERASSIGNEDIDENTITYRESOURCEID
require APPCONFIGCONNSTRING
require LOGANALYTICSWORKSPACEID
require LOGANALYTICSWORKSPACEKEY
require AUTOMATION_NAME
require WEBAPPSUBNETRESOURCEID
require AUTOMATIONSUBNETRESOURCEID
require AUTREPLICAS
require WEBAPPREPLICAS
require APPENV

CONFIG_FILE="${CONFIG_FILE:-${BUILD_SOURCESDIRECTORY}/deploy/config.json}"
DEPLOY_SETTINGS_FILE="${DEPLOY_SETTINGS_FILE:-${BUILD_SOURCESDIRECTORY}/deploy/scripts/settings.json}"
INGRESS_TYPE="${INGRESS_TYPE:-external}"

if [ ! -f "$CONFIG_FILE" ]; then
  echo "Missing config.json at: $CONFIG_FILE" >&2
  exit 1
fi
if [ ! -f "$DEPLOY_SETTINGS_FILE" ]; then
  echo "Missing deploy settings JSON at: $DEPLOY_SETTINGS_FILE" >&2
  exit 1
fi

IS_TIMER="$(jq -r '(.is_timer // false) | tostring' "$CONFIG_FILE")"
CRON_EXPRESSION="$(jq -r '.cron_expression // ""' "$CONFIG_FILE")"
CUSTOMER_NAME="$(jq -r '.Customer_Name // .customer_name // .customerName // empty' "$CONFIG_FILE" 2>/dev/null || true)"
TARGET_PORT="$(jq -r '.target_port // ""' "$CONFIG_FILE")"
APP_TYPE="$(jq -r '.app_type // ""' "$CONFIG_FILE")"

if [ -z "${CUSTOMER_NAME:-}" ] || [ "${CUSTOMER_NAME:-}" = "null" ]; then
  echo "config.json must include Customer_Name (or customer_name/customerName)." >&2
  exit 1
fi
if ! echo "$APP_TYPE" | grep -Eq '^(WebApp|AUT)$'; then
  echo "Invalid APP_TYPE value: '$APP_TYPE'. Expected 'WebApp' or 'AUT'" >&2
  exit 1
fi
if ! echo "$TARGET_PORT" | grep -Eq '^[0-9]+$' || [ "$TARGET_PORT" -lt 1 ] || [ "$TARGET_PORT" -gt 65535 ]; then
  echo "Invalid target_port value in config.json: '$TARGET_PORT' (expected 1-65535)" >&2
  exit 1
fi

TRIGGER_TYPE="$(jq -r '.trigger_type // ""' "$DEPLOY_SETTINGS_FILE")"
CPU="$(jq -r '.cpu // ""' "$DEPLOY_SETTINGS_FILE")"
MEMORY="$(jq -r '.memory // ""' "$DEPLOY_SETTINGS_FILE")"
SETTINGS_MIN_REPLICAS="$(jq -r '.min_replicas // ""' "$DEPLOY_SETTINGS_FILE")"

# ============================================
# Runtime overrides from pipeline parameters
# These override settings.json values if provided
# 'default' or empty = use settings.json value
# ============================================
echo ""
echo "=== Checking Pipeline Overrides ==="

# Parse combined resource size (format: 0.25CPU::::0.5Gi)
if [ -n "${OVERRIDE_RESOURCE_SIZE:-}" ] && [ "${OVERRIDE_RESOURCE_SIZE}" != "default" ]; then
  OVERRIDE_CPU="${OVERRIDE_RESOURCE_SIZE%%CPU::::*}"
  OVERRIDE_MEMORY="${OVERRIDE_RESOURCE_SIZE##*::::}"
  echo "  CPU: $CPU -> $OVERRIDE_CPU (pipeline override)"
  echo "  MEMORY: $MEMORY -> $OVERRIDE_MEMORY (pipeline override)"
  CPU="$OVERRIDE_CPU"
  MEMORY="$OVERRIDE_MEMORY"
fi

if [ -n "${OVERRIDE_MIN_REPLICAS:-}" ] && [ "${OVERRIDE_MIN_REPLICAS}" != "default" ]; then
  echo "  MIN_REPLICAS: ${SETTINGS_MIN_REPLICAS:-<not set>} -> $OVERRIDE_MIN_REPLICAS (pipeline override)"
  SETTINGS_MIN_REPLICAS="$OVERRIDE_MIN_REPLICAS"
fi

# Always use single revision mode (old revisions are preserved but deactivated)
# This saves resources while still allowing rollback by reactivating old revisions
REVISION_MODE="single"

echo "=== End Pipeline Overrides ==="
echo ""

echo "IS_TIMER: $IS_TIMER"
echo "CRON_EXPRESSION: $CRON_EXPRESSION"
echo "CUSTOMER_NAME: $CUSTOMER_NAME"
echo "TRIGGER_TYPE: $TRIGGER_TYPE"
echo "CPU: $CPU"
echo "MEMORY: $MEMORY"
echo "TARGET_PORT: $TARGET_PORT"
echo "INGRESS_TYPE: $INGRESS_TYPE"
echo "APP_TYPE: $APP_TYPE"
echo "REVISION_MODE: $REVISION_MODE"
echo "AUTOMATION_NAME: ${AUTOMATION_NAME:-<not set>}"
echo "WEBAPPSUBNETRESOURCEID: ${WEBAPPSUBNETRESOURCEID:-<not set>}"
echo "AUTOMATIONSUBNETRESOURCEID: ${AUTOMATIONSUBNETRESOURCEID:-<not set>}"

if [ -z "${CPU:-}" ] || [ -z "${MEMORY:-}" ] || [ -z "${TRIGGER_TYPE:-}" ]; then
  echo "settings.json must include trigger_type, cpu and memory." >&2
  exit 1
fi

az extension add --name containerapp --upgrade --allow-preview true

ensure_containerapp_ingress() {
  # Keep ingress/target-port in sync even for existing apps.
  az containerapp ingress enable \
    --name "$CONTAINERNAME" \
    --resource-group "$RESOURCEGROUP" \
    --type "$INGRESS_TYPE" \
    --target-port "$TARGET_PORT" >/dev/null
}

ensure_containerapp_secrets() {
  # Keep secret refs in sync (avoids relying on `containerapp update --secrets` behavior).
  az containerapp secret set \
    --name "$CONTAINERNAME" \
    --resource-group "$RESOURCEGROUP" \
    --secrets "appcfg=keyvaultref:${APPCONFIGCONNSTRING},identityref:${USERASSIGNEDIDENTITYRESOURCEID}" >/dev/null
}

ensure_containerapp_job_secrets() {
  # Keep secret refs in sync (avoids relying on `containerapp job update --secrets` behavior).
  az containerapp job secret set \
    --name "$CONTAINERNAME" \
    --resource-group "$RESOURCEGROUP" \
    --secrets "appcfg=keyvaultref:${APPCONFIGCONNSTRING},identityref:${USERASSIGNEDIDENTITYRESOURCEID}" >/dev/null
}

if ! az group show --name "$RESOURCEGROUP" >/dev/null 2>&1; then
  echo "Resource group does not exist. Create it before deploying: $RESOURCEGROUP" >&2
  # az group create --name "$RESOURCEGROUP" --location "$REGION"
fi

if [ "$APP_TYPE" = "AUT" ]; then
  CONTAINERENVIRONMENTNAME="$CONTAINERAUTENVIRONMENTNAME"
  INFRASTRUCTURESUBNETRESOURCEID="$AUTOMATIONSUBNETRESOURCEID"
  DEFAULT_REPLICAS="$AUTREPLICAS"
  echo "Selected AUT environment: $CONTAINERENVIRONMENTNAME"
elif [ "$APP_TYPE" = "WebApp" ]; then
  CONTAINERENVIRONMENTNAME="$CONTAINERWEBAPPENVIRONMENTNAME"
  INFRASTRUCTURESUBNETRESOURCEID="$WEBAPPSUBNETRESOURCEID"
  DEFAULT_REPLICAS="$WEBAPPREPLICAS"
  echo "Selected WebApp environment: $CONTAINERENVIRONMENTNAME"
else
  echo "Unexpected APP_TYPE value: '$APP_TYPE'. Expected 'WebApp' or 'AUT'" >&2
  exit 1
fi

# Priority: pipeline override > settings.json > variable group (AUTREPLICAS/WEBAPPREPLICAS)
if [ -n "${SETTINGS_MIN_REPLICAS:-}" ]; then
  MIN_REPLICAS="$SETTINGS_MIN_REPLICAS"
  echo "MIN_REPLICAS: $MIN_REPLICAS (from settings.json or pipeline override)"
else
  MIN_REPLICAS="$DEFAULT_REPLICAS"
  echo "MIN_REPLICAS: $MIN_REPLICAS (from variable group)"
fi
echo "Using Min Replicas: ${MIN_REPLICAS:-<none>}"

if ! az containerapp env show --name "$CONTAINERENVIRONMENTNAME" --resource-group "$RESOURCEGROUP" >/dev/null 2>&1; then
  echo "Container app environment does not exist. Creating it now."
  az containerapp env create \
    --name "$CONTAINERENVIRONMENTNAME" \
    --resource-group "$RESOURCEGROUP" \
    --location "$REGION" \
    --infrastructure-subnet-resource-id "${INFRASTRUCTURESUBNETRESOURCEID:-}" \
    --logs-workspace-id "${LOGANALYTICSWORKSPACEID:-}" \
    --logs-workspace-key "${LOGANALYTICSWORKSPACEKEY:-}"
fi

IMAGE="${AZURECONTAINERREGISTRY}/${CONTAINERNAME}:${BUILD_BUILDID}"
COMMON_ENV_VARS=(APP_CONFIGURATION_CONNECTION_STRING=secretref:appcfg)
COMMON_ENV_VARS+=(APPLICATION_ENVIRONMENT="${APPENV}")
COMMON_ENV_VARS+=(AUTOMATION_NAME="${AUTOMATION_NAME}")

# ============================================
# Append custom environment variables from pipeline
# Format: KEY1=value1;;KEY2=value2;;KEY3=value3
# Uses ;; as delimiter to support values containing commas
# ============================================
if [ -n "${CUSTOM_ENV_VARS:-}" ] && [ "${CUSTOM_ENV_VARS}" != "none" ]; then
  echo "Adding custom environment variables from pipeline..."
  # Split on ;; delimiter (supports values with commas, colons, etc.)
  while IFS= read -r var; do
    # Trim whitespace
    var="$(echo "$var" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    if [ -n "$var" ] && [[ "$var" == *"="* ]]; then
      key="${var%%=*}"
      echo "  + $key=<value>"
      COMMON_ENV_VARS+=("$var")
    fi
  done <<< "$(echo "$CUSTOM_ENV_VARS" | sed 's/;;/\n/g')"
  echo "Total env vars: ${#COMMON_ENV_VARS[@]}"
fi

if [ "${IS_TIMER}" = "true" ]; then
  if [ -z "${TRIGGER_TYPE:-}" ]; then
    echo "is_timer=true but trigger_type is empty (from settings JSON)." >&2
    exit 1
  fi
  if [ "${TRIGGER_TYPE}" = "Schedule" ]; then
    if [ -z "${CRON_EXPRESSION:-}" ]; then
      echo "trigger_type=Schedule but cron_expression is empty (from config.json)." >&2
      exit 1
    fi
  elif [ -n "${CRON_EXPRESSION:-}" ]; then
    echo "Note: cron_expression is set in config.json but trigger_type is '${TRIGGER_TYPE}'. Ignoring cron_expression."
  fi

  if az containerapp job show --name "$CONTAINERNAME" --resource-group "$RESOURCEGROUP" >/dev/null 2>&1; then
    echo "Container App Job exists. Updating image + env vars."
    # ensure_containerapp_job_secrets
    CRON_ARGS=()
    if [ "${TRIGGER_TYPE}" = "Schedule" ]; then
      CRON_ARGS+=(--cron-expression "$CRON_EXPRESSION")
    fi
    az containerapp job update \
      --name "$CONTAINERNAME" \
      --resource-group "$RESOURCEGROUP" \
      --image "$IMAGE" \
      --cpu "$CPU" --memory "$MEMORY" \
      --set-env-vars "${COMMON_ENV_VARS[@]}" \
      "${CRON_ARGS[@]}" >/dev/null
  else
    echo "Container App Job does not exist. Creating it (Schedule)."
    CRON_ARGS=()
    if [ "${TRIGGER_TYPE}" = "Schedule" ]; then
      CRON_ARGS+=(--cron-expression "$CRON_EXPRESSION")
    fi
    az containerapp job create \
      --name "$CONTAINERNAME" \
      --resource-group "$RESOURCEGROUP" \
      --image "$IMAGE" \
      --cpu "$CPU" --memory "$MEMORY" \
      --environment "$CONTAINERENVIRONMENTNAME" \
      --registry-server "$AZURECONTAINERREGISTRY" \
      --trigger-type "$TRIGGER_TYPE" \
      --user-assigned "$USERASSIGNEDIDENTITYRESOURCEID" \
      --secrets "appcfg=keyvaultref:${APPCONFIGCONNSTRING},identityref:${USERASSIGNEDIDENTITYRESOURCEID}" \
      --env-vars "${COMMON_ENV_VARS[@]}" \
      "${CRON_ARGS[@]}" >/dev/null
  fi

  echo "Verifying Container App Job..."
  az containerapp job show --name "$CONTAINERNAME" --resource-group "$RESOURCEGROUP"
else
  # `az containerapp show` identifies the app by (resource group, name).
  # Passing `--environment` here can make the check fail even when the app exists.
  if az containerapp show --name "$CONTAINERNAME" --resource-group "$RESOURCEGROUP" >/dev/null 2>&1; then
    echo "Container App exists. Updating image + ingress/target port + env vars."
    
    # Retry logic for transient ACR/image pull failures
    MAX_RETRIES=3
    RETRY_DELAY=30
    UPDATE_SUCCESS=false
    
    for attempt in $(seq 1 $MAX_RETRIES); do
      echo "=== Update attempt $attempt of $MAX_RETRIES ==="
      
      if az containerapp update \
        --name "$CONTAINERNAME" \
        --resource-group "$RESOURCEGROUP" \
        --image "$IMAGE" \
        --cpu "$CPU" --memory "$MEMORY" \
        --min-replicas "$MIN_REPLICAS" \
        --revisions-mode "$REVISION_MODE" \
        --set-env-vars "${COMMON_ENV_VARS[@]}"; then
        UPDATE_SUCCESS=true
        break
      else
        if [ $attempt -lt $MAX_RETRIES ]; then
          echo "⚠️ Update failed (likely transient ACR/image pull issue). Retrying in ${RETRY_DELAY}s..."
          sleep $RETRY_DELAY
        fi
      fi
    done
    
    if [ "$UPDATE_SUCCESS" = false ]; then
      echo "❌ Container App update failed after $MAX_RETRIES attempts"
      exit 1
    fi
    
    ensure_containerapp_ingress
  else
    echo "Container App does not exist. Creating it now."
    
    # Retry logic for transient ACR/image pull failures
    MAX_RETRIES=3
    RETRY_DELAY=30
    CREATE_SUCCESS=false
    
    for attempt in $(seq 1 $MAX_RETRIES); do
      echo "=== Create attempt $attempt of $MAX_RETRIES ==="
      
      if az containerapp create \
        --name "$CONTAINERNAME" \
        --resource-group "$RESOURCEGROUP" \
        --image "$IMAGE" \
        --cpu "$CPU" --memory "$MEMORY" \
        --min-replicas "$MIN_REPLICAS" \
        --revisions-mode "$REVISION_MODE" \
        --environment "$CONTAINERENVIRONMENTNAME" \
        --registry-server "$AZURECONTAINERREGISTRY" \
        --ingress "$INGRESS_TYPE" \
        --target-port "$TARGET_PORT" \
        --user-assigned "$USERASSIGNEDIDENTITYRESOURCEID" \
        --secrets "appcfg=keyvaultref:${APPCONFIGCONNSTRING},identityref:${USERASSIGNEDIDENTITYRESOURCEID}" \
        --env-vars "${COMMON_ENV_VARS[@]}"; then
        CREATE_SUCCESS=true
        break
      else
        if [ $attempt -lt $MAX_RETRIES ]; then
          echo "⚠️ Create failed (likely transient ACR/image pull issue). Retrying in ${RETRY_DELAY}s..."
          sleep $RETRY_DELAY
        fi
      fi
    done
    
    if [ "$CREATE_SUCCESS" = false ]; then
      echo "❌ Container App creation failed after $MAX_RETRIES attempts"
      exit 1
    fi

    BIND_SCRIPT="${BUILD_SOURCESDIRECTORY}/deploy/scripts/bind-custom-domain.sh"
    if [ ! -f "${BIND_SCRIPT}" ]; then
        echo "Missing custom domain bind script at: ${BIND_SCRIPT}" >&2
        exit 1
    fi
      echo "Binding custom hostname (create-only) via: ${BIND_SCRIPT}"
      bash "${BIND_SCRIPT}"
  fi

  echo "Verifying Container App..."
  az containerapp show --name "$CONTAINERNAME" --resource-group "$RESOURCEGROUP"
fi
