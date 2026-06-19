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
require BUILD_SOURCEBRANCHNAME
require BUILD_REPOSITORY_NAME

BRANCH="${BUILD_SOURCEBRANCHNAME}"
case "$BRANCH" in
  uat|staging|main) ;;
  *)
    echo "Skipping hub update for branch: $BRANCH"
    exit 0
    ;;
esac

if ! command -v jq >/dev/null 2>&1; then
  echo "Missing required dependency: jq" >&2
  exit 1
fi

SSH_KEY_PATH="${SSH_KEY_PATH:-${HOME}/.ssh/automation-key}"
if [ ! -f "$SSH_KEY_PATH" ]; then
  echo "Missing SSH key at: $SSH_KEY_PATH" >&2
  echo "Provision this key on the agent, or switch to Azure DevOps Secure Files + InstallSSHKey@0." >&2
  exit 1
fi

mkdir -p "${HOME}/.ssh"
touch "${HOME}/.ssh/known_hosts"
ssh-keyscan -H ssh.dev.azure.com vs-ssh.visualstudio.com >> "${HOME}/.ssh/known_hosts" 2>/dev/null || true
export GIT_SSH_COMMAND="ssh -i ${SSH_KEY_PATH} -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=${HOME}/.ssh/known_hosts"

HUB_REPO_URL="${HUB_REPO_URL:-git@ssh.dev.azure.com:v3/joblogicltd/JobLogic%20Automations/container-automations-hub}"
HUB_DIR="${HUB_DIR:-${BUILD_SOURCESDIRECTORY}/.hubrepo}"

REPO_NAME="${BUILD_REPOSITORY_NAME##*/}"

CONFIG_FILE="${BUILD_SOURCESDIRECTORY}/deploy/config.json"
CUSTOMER_NAME="$(jq -r '.Customer_Name // .customer_name // .customerName // empty' "$CONFIG_FILE" 2>/dev/null || true)"
if [ -z "${CUSTOMER_NAME:-}" ] || [ "${CUSTOMER_NAME:-}" = "null" ]; then
  echo "config.json must include Customer_Name (or customer_name/customerName) for hub submodule pathing." >&2
  exit 1
fi

SUBMODULE_PATH="${CUSTOMER_NAME}/${REPO_NAME}"
SELF_REPO_URL="git@ssh.dev.azure.com:v3/joblogicltd/JobLogic%20Automations/${REPO_NAME}"

rm -rf "$HUB_DIR"
mkdir -p "$HUB_DIR"

echo "Cloning hub repo: $HUB_REPO_URL"
git ls-remote "$HUB_REPO_URL" >/dev/null
git clone "$HUB_REPO_URL" "$HUB_DIR"
cd "$HUB_DIR"

git config user.email "build@joblogicltd"
git config user.name "azure-pipelines"

git fetch origin --prune

if git show-ref --verify --quiet "refs/remotes/origin/${BRANCH}"; then
  git checkout -B "${BRANCH}" "origin/${BRANCH}"
else
  echo "Hub branch '${BRANCH}' does not exist. Creating from origin/main."
  if git show-ref --verify --quiet "refs/remotes/origin/main"; then
    git checkout -B "${BRANCH}" "origin/main"
  else
    git checkout -B "${BRANCH}"
  fi
  git push -u origin "${BRANCH}"
fi

if [ -f .gitmodules ] && git config -f .gitmodules --get-regexp '^submodule\..*\.path$' | awk '{print $2}' | grep -Fxq "$SUBMODULE_PATH"; then
  echo "Submodule exists at path: $SUBMODULE_PATH. Updating to latest commit on branch '${BRANCH}'."
  git submodule set-branch --branch "${BRANCH}" "$SUBMODULE_PATH" >/dev/null 2>&1 || true
  git submodule sync --recursive "$SUBMODULE_PATH"
  git submodule update --init --remote --recursive "$SUBMODULE_PATH"
else
  echo "Submodule missing at path: $SUBMODULE_PATH. Adding it."
  mkdir -p "$(dirname "$SUBMODULE_PATH")"
  git submodule add -b "${BRANCH}" "$SELF_REPO_URL" "$SUBMODULE_PATH"
  git submodule set-branch --branch . "$SUBMODULE_PATH"
fi

if [ -z "$(git status --porcelain)" ]; then
  echo "No hub changes to commit."
  exit 0
fi

git add "$SUBMODULE_PATH"
if [ -f .gitmodules ]; then
  git add .gitmodules
fi

if git diff --cached --quiet; then
  echo "Detected hub changes but nothing staged for commit. Current status:" >&2
  git status >&2
  exit 1
fi

git commit -m "Update ${REPO_NAME} submodule on ${BRANCH}"
git push origin "${BRANCH}"
