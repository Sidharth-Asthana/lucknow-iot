#!/usr/bin/env bash
# create_github_repo.sh
# Run this once after authenticating: gh auth login
# It creates the remote repo and pushes the local commit.

set -euo pipefail

REPO_NAME="lucknow-iot"
DESCRIPTION="Local-first IoT dashboard for a smart self-sufficient residence in Lucknow, India. HA + MQTT + Frigate + ESP32 + KNX."
VISIBILITY="public"   # change to "private" if you prefer

echo "==> Creating GitHub repository: $REPO_NAME"
gh repo create "$REPO_NAME" \
  --description "$DESCRIPTION" \
  --"$VISIBILITY" \
  --source "$(dirname "$0")/.." \
  --remote origin \
  --push

echo ""
echo "==> Done! Your repo is live at:"
gh repo view --json url -q .url
