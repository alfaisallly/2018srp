#!/bin/bash
# Helper script: lists Swift source files for manual Xcode project setup.
# Run on Mac after copying sources into an Xcode iOS App project.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "=== WiFi Manager — Source Files ==="
find "$ROOT" -name "*.swift" | sort

echo ""
echo "=== Required Xcode Capabilities ==="
echo "  • Access WiFi Information"
echo "  • Location When In Use (Info.plist key already included)"

echo ""
echo "=== Next Steps ==="
echo "  1. Create iOS App project in Xcode (SwiftUI, iOS 17+)"
echo "  2. Replace default sources with files listed above"
echo "  3. Add WiFiManager.entitlements to Code Signing Entitlements"
echo "  4. Run on a physical iPhone connected to Wi-Fi"
