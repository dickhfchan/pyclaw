#!/bin/bash
# One-time setup: registers the MySub native messaging host with Chrome and Arc.
# Usage: ./native/install.sh <extension-id>
#
# Find your extension ID in the MySub popup (bottom-right of the settings
# footer, click to copy) or at chrome://extensions / arc://extensions.

set -euo pipefail

EXT_ID="${1:-}"
if [ -z "$EXT_ID" ]; then
    echo "Usage: $0 <extension-id>"
    echo ""
    echo "Find your ID:"
    echo "  • Open the MySub popup → look at the bottom-right of the settings bar"
    echo "  • Or visit chrome://extensions and find MySub"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOST_SCRIPT="$SCRIPT_DIR/mysub_host.py"
HOST_NAME="com.mysub.downloader"

chmod +x "$HOST_SCRIPT"

MANIFEST='{
    "name": "'"$HOST_NAME"'",
    "description": "MySub yt-dlp download bridge",
    "path": "'"$HOST_SCRIPT"'",
    "type": "stdio",
    "allowed_origins": ["chrome-extension://'"$EXT_ID"'/"]
}'

install_for() {
    local dir="$1" label="$2"
    mkdir -p "$dir"
    echo "$MANIFEST" > "$dir/$HOST_NAME.json"
    echo "  ✓ $label"
}

install_for "$HOME/Library/Application Support/Google/Chrome/NativeMessagingHosts" "Chrome"
install_for "$HOME/Library/Application Support/Arc/User Data/NativeMessagingHosts"  "Arc"

echo ""
echo "Native host installed."
echo "  script : $HOST_SCRIPT"
echo "  allowed: chrome-extension://$EXT_ID/"
echo ""
echo "Reload MySub in your browser, then click ↓ on any video card."
