#!/usr/bin/env bash
# v1.6 §15 — macOS codesign + notarize + staple for signed .dmg release artifact.
# Requires env: APPLE_ID, APPLE_TEAM_ID, APPLE_APP_PASSWORD (app-specific), SIGNING_IDENTITY.
set -euo pipefail

: "${APPLE_ID:?APPLE_ID is required}"
: "${APPLE_TEAM_ID:?APPLE_TEAM_ID is required}"
: "${APPLE_APP_PASSWORD:?APPLE_APP_PASSWORD is required}"
: "${SIGNING_IDENTITY:?SIGNING_IDENTITY is required (Developer ID Application: Name (TEAMID))}"

BUNDLE="${1:-dist/multicap.app}"
DMG="${2:-dist/multicap.dmg}"
ENTITLEMENTS="$(dirname "$0")/entitlements.plist"

if [[ ! -d "$BUNDLE" ]]; then
  echo "Bundle not found: $BUNDLE" >&2
  exit 1
fi

echo "==> codesign (hardened runtime, entitlements)"
codesign --force --deep --options runtime \
  --entitlements "$ENTITLEMENTS" \
  --sign "$SIGNING_IDENTITY" \
  --timestamp \
  "$BUNDLE"

echo "==> verify codesign"
codesign --verify --deep --strict --verbose=2 "$BUNDLE"
spctl --assess --type execute --verbose=2 "$BUNDLE" || true

echo "==> create .dmg"
rm -f "$DMG"
hdiutil create -volname multicap -srcfolder "$BUNDLE" -ov -format UDZO "$DMG"

echo "==> codesign .dmg"
codesign --force --sign "$SIGNING_IDENTITY" --timestamp "$DMG"

echo "==> submit to Apple notary service"
xcrun notarytool submit "$DMG" \
  --apple-id "$APPLE_ID" \
  --team-id "$APPLE_TEAM_ID" \
  --password "$APPLE_APP_PASSWORD" \
  --wait

echo "==> staple ticket"
xcrun stapler staple "$DMG"
xcrun stapler validate "$DMG"

echo "==> done: $DMG"
