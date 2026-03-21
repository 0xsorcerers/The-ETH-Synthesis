#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-https://synthesis.devfolio.co}"
SESSION_FILE="${SESSION_FILE:-tmp/synthesis_session.env}"
ACTION="${1:-}"

if [[ -z "${ACTION}" ]]; then
  echo "Usage: $0 <catalog|whoami|team|cache-session|save-env|create|update|publish|verify|transfer-init|transfer-confirm>"
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

save_session_kv() {
  local key="$1"
  local value="$2"
  mkdir -p "$(dirname "${SESSION_FILE}")"
  touch "${SESSION_FILE}"
  if rg -q "^${key}=" "${SESSION_FILE}"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "${SESSION_FILE}"
  else
    echo "${key}=${value}" >> "${SESSION_FILE}"
  fi
}

require_jq() {
  if ! command -v jq >/dev/null 2>&1; then
    echo "This script requires jq to parse API responses." >&2
    exit 1
  fi
}

case "$ACTION" in
  catalog)
    curl -sS "${BASE_URL}/catalog?page=1&limit=50" | jq
    ;;
  whoami)
    require SYNTH_API_KEY
    curl -sS "${BASE_URL}/participants/me" \
      -H "$(auth_header)" | jq
    ;;
  team)
    require SYNTH_API_KEY
    require TEAM_UUID
    curl -sS "${BASE_URL}/teams/${TEAM_UUID}" \
      -H "$(auth_header)" | jq
    ;;
  cache-session)
    require SYNTH_API_KEY
    require_jq

    participant_json="$(curl -sS "${BASE_URL}/participants/me" -H "$(auth_header)")"
    team_uuid="$(echo "${participant_json}" | jq -r '.teamUUID // .teamUUIDs[0] // .team.uuid // .teamUUIDList[0] // empty')"

    if [[ -z "${team_uuid}" ]]; then
      echo "Could not infer TEAM_UUID from /participants/me response:" >&2
      echo "${participant_json}" | jq >&2
      exit 1
    fi

    team_json="$(curl -sS "${BASE_URL}/teams/${team_uuid}" -H "$(auth_header)")"
    project_uuid="$(echo "${team_json}" | jq -r '.projectUUID // .project.uuid // .projects[0].uuid // .projects[0].projectUUID // empty')"

    save_session_kv TEAM_UUID "${team_uuid}"
    if [[ -n "${project_uuid}" ]]; then
      save_session_kv PROJECT_UUID "${project_uuid}"
    fi

    echo "Saved session values to ${SESSION_FILE}:"
    echo "- TEAM_UUID=${team_uuid}"
    if [[ -n "${project_uuid}" ]]; then
      echo "- PROJECT_UUID=${project_uuid}"
    else
      echo "- PROJECT_UUID not found (create draft first)"
    fi
    ;;
  save-env)
    mkdir -p "$(dirname "${SESSION_FILE}")"
    target_env="${TARGET_ENV_FILE:-.env.synthesis.local}"
    cat > "${target_env}" <<ENV
# Synthesis local session cache (generated)
# Keep this file local. It is ignored by git.
SYNTH_API_KEY=${SYNTH_API_KEY:-}
TEAM_UUID=${TEAM_UUID:-}
PROJECT_UUID=${PROJECT_UUID:-}
TRACK_UUIDS=${TRACK_UUIDS:-}
OWNER_WALLET=${OWNER_WALLET:-0x8B40FC00D483b8A6A31539BbB399B14e1d36E454}
REGISTRATION_TX=0x3be69aa1e843e835e794ed5a7bb1b46e91793c411e50c33e366cabf36970e02c
MINT_TX_OWNER=0x6FFa1e00509d8B625c2F061D7dB07893B37199BC
PROJECT_NAME=Skynet by 0xSorcerer
MODEL=gpt-5.2-codex
AGENT_HARNESS=codex-cli
REPO_URL=${REPO_URL:-https://github.com/0xsorcerers/The-ETH-Synthesis.git}
MOLTBOOK_POST_URL=${MOLTBOOK_POST_URL:-}
BASE_URL=${BASE_URL}
SESSION_FILE=${SESSION_FILE}
ENV
    echo "Wrote local env snapshot: ${target_env}"
    ;;
  create)
    require SYNTH_API_KEY
    require TEAM_UUID
    require TRACK_UUIDS
    require REPO_URL
    require MOLTBOOK_POST_URL

    tmp_payload="$(mktemp)"
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
