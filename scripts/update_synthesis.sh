#!/bin/bash
# Synthesis Project Update Script
# Run this in Git Bash or WSL

SYNTH_API_KEY="sk-synth-dab98a7643c4bf884233166748a81ead5af739bfd3b2c18c"
PROJECT_UUID="7139821eaf054b31ac6e42128e40b6be"

# Updated description with 'human and agentic review'
DESCRIPTION="Skynet's AI Tax Agent Protocol (SATA Protocol) is an autonomous crypto tax compliance copilot that ingests wallet/exported transaction activity, classifies events, applies jurisdiction-aware tax treatment, and generates transparent report artifacts for human and AI agentic review."

# Track UUIDs
TRACK_UUIDS='["6f0e3d7dcadf4ef080d3f424963caff5","9bd8b3fde4d0458698d618daf496d1c7","10bd47fac07e4f85bda33ba482695b24"]'

# Railway deployed URL
DEPLOYED_URL="https://sata-protocol.up.railway.app/"

# Update payload
PAYLOAD=$(cat <<EOF
{
  "description": "$DESCRIPTION",
  "trackUUIDs": $TRACK_UUIDS,
  "deployedURL": "$DEPLOYED_URL"
}
EOF
)

echo "Updating project..."
echo "Payload: $PAYLOAD"
echo ""

# Try POST
curl -X POST "https://synthesis.devfolio.co/api/v1/projects/$PROJECT_UUID" \
  -H "Authorization: Bearer $SYNTH_API_KEY" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" \
  -v
