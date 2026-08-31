#!/bin/bash
# One-time setup: registers the MySub native messaging host with Chrome.
# Usage: ./native/install.sh <extension-id>
#
# Find your extension ID in the MySub popup (bottom-right of the settings
# footer, click to copy) or at chrome://extensions.

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
NMH_DIR="$HOME/Library/Application Support/Google/Chrome/NativeMessagingHosts"

chmod +x "$HOST_SCRIPT"
mkdir -p "$NMH_DIR"

cat > "$NMH_DIR/$HOST_NAME.json" << EOF
{
    "name": "$HOST_NAME",
    "description": "MySub yt-dlp download bridge",
    "path": "$HOST_SCRIPT",
    "type": "stdio",
    "allowed_origins": ["chrome-extension://$EXT_ID/"]
}
EOF

echo "✓ Native host installed"
echo "  script : $HOST_SCRIPT"
echo "  manifest: $NMH_DIR/$HOST_NAME.json"
echo "  allowed : chrome-extension://$EXT_ID/"
echo ""
echo "Reload MySub at chrome://extensions, then click ↓ on any video card."
