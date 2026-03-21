#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-https://synthesis.devfolio.co}"
ACTION="${1:-}"

if [[ -z "${ACTION}" ]]; then
  echo "Usage: $0 <catalog|team|create|update|publish|verify|transfer-init|transfer-confirm>"
  exit 1
fi

require() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required env var: ${name}" >&2
    exit 1
  fi
}

auth_header() {
  echo "Authorization: Bearer ${SYNTH_API_KEY}"
}

case "$ACTION" in
  catalog)
    curl -sS "${BASE_URL}/catalog?page=1&limit=50" | jq
    ;;
  team)
    require SYNTH_API_KEY
    require TEAM_UUID
    curl -sS "${BASE_URL}/teams/${TEAM_UUID}" \
      -H "$(auth_header)" | jq
    ;;
  create)
    require SYNTH_API_KEY
    require TEAM_UUID
    require TRACK_UUIDS
    require REPO_URL
    # MOLTBOOK_POST_URL is optional at draft create time

    tmp_payload="$(mktemp)"
    if [[ -n "${MOLTBOOK_POST_URL:-}" ]]; then
      jq \
        --arg teamUUID "${TEAM_UUID}" \
        --arg repoURL "${REPO_URL}" \
        --arg moltbookPostURL "${MOLTBOOK_POST_URL}" \
        --argjson trackUUIDs "${TRACK_UUIDS}" \
        '.teamUUID=$teamUUID
         | .repoURL=$repoURL
         | .trackUUIDs=$trackUUIDs
         | .submissionMetadata.moltbookPostURL=$moltbookPostURL' \
        docs/templates/synthesis-project-payload.json > "${tmp_payload}"
    else
      jq \
        --arg teamUUID "${TEAM_UUID}" \
        --arg repoURL "${REPO_URL}" \
        --argjson trackUUIDs "${TRACK_UUIDS}" \
        '.teamUUID=$teamUUID
         | .repoURL=$repoURL
         | .trackUUIDs=$trackUUIDs
         | (.submissionMetadata |= del(.moltbookPostURL))' \
        docs/templates/synthesis-project-payload.json > "${tmp_payload}"
    fi

    curl -sS -X POST "${BASE_URL}/projects" \
      -H "$(auth_header)" \
      -H "Content-Type: application/json" \
      --data-binary @"${tmp_payload}" | jq
    ;;
  update)
    require SYNTH_API_KEY
    require PROJECT_UUID

    curl -sS -X POST "${BASE_URL}/projects/${PROJECT_UUID}" \
      -H "$(auth_header)" \
      -H "Content-Type: application/json" \
      --data-binary @docs/templates/synthesis-project-payload.json | jq
    ;;
  publish)
    require SYNTH_API_KEY
    require PROJECT_UUID

    curl -sS -X POST "${BASE_URL}/projects/${PROJECT_UUID}/publish" \
      -H "$(auth_header)" | jq
    ;;
  verify)
    require PROJECT_UUID

    echo "--- Project ---"
    curl -sS "${BASE_URL}/projects/${PROJECT_UUID}" | jq
    echo
    echo "--- Public Listing ---"
    curl -sS "${BASE_URL}/projects?page=1&limit=20" | jq
    ;;
  transfer-init)
    require SYNTH_API_KEY
    require OWNER_WALLET

    curl -sS -X POST "${BASE_URL}/participants/me/transfer/init" \
      -H "$(auth_header)" \
      -H "Content-Type: application/json" \
      -d "{\"targetOwnerAddress\":\"${OWNER_WALLET}\"}" | jq
    ;;
  transfer-confirm)
    require SYNTH_API_KEY
    require OWNER_WALLET
    require TRANSFER_TOKEN

    curl -sS -X POST "${BASE_URL}/participants/me/transfer/confirm" \
      -H "$(auth_header)" \
      -H "Content-Type: application/json" \
      -d "{\"transferToken\":\"${TRANSFER_TOKEN}\",\"targetOwnerAddress\":\"${OWNER_WALLET}\"}" | jq
    ;;
  *)
    echo "Unknown action: ${ACTION}" >&2
    exit 1
    ;;
esac
