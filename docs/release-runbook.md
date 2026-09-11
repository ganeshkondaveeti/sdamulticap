# Phase 10 Release, Signing, Rollback, and Recall Runbook

This runbook implements `docs/implementation-plan.md` §15 for SC-10 releases.
Build all artifacts from one signed git tag and preserve PySide6/Qt dynamic
linking by using PyInstaller one-folder mode only.

## Prerequisites

The release tag must pass:

```bash
uv run python -m multicap --smoke
uv run pytest tests/ui
```

Release hosts and required tools:

| Host | Artifacts | Tools | Signing material |
|---|---|---|---|
| macOS | `.dmg` | PyInstaller, `hdiutil`, `codesign`, `xcrun notarytool` | `SIGNING_IDENTITY`, `APPLE_ID`, `APPLE_TEAM_ID`, `APPLE_APP_PASSWORD` |
| Windows | `.exe`, `.msi` | PyInstaller, Inno Setup, WiX Toolset, `signtool` | `WINDOWS_CERT_PATH`, `WINDOWS_CERT_PASSWORD`, optional `WINDOWS_TIMESTAMP_URL` |
| Linux | `.deb`, AppImage | PyInstaller, `dpkg-deb`, `dpkg-sig`, `appimagetool`, `gpg` | `DPKG_SIG_KEY_ID`, `GPG_SIGNING_KEY_ID` |

Local unsigned smoke artifacts are allowed only before release-channel upload:

```bash
uv run python packaging/release.py --clean --unsigned-local
```

## Build and smoke

Run on each OS runner from the same git tag:

```bash
uv run python packaging/release.py --clean
```

The builder performs these gates in order:

1. `uv run --with pyinstaller pyinstaller packaging/pyinstaller/multicap.spec --noconfirm`
2. Launches the bundled app with `--smoke` and requires `multicap GUI smoke ok`.
3. Creates the OS-native wrapper: `.dmg`, Windows `.exe` + `.msi`, or Linux `.deb` + AppImage.
4. Signs and notarizes when the host requires it.
5. Writes one CycloneDX SBOM per produced artifact under `artifacts/sbom/`.

## Signing and notarization checks

Before publishing, verify signatures independently:

```bash
# macOS
codesign --verify --deep --strict --verbose=2 artifacts/*.dmg
xcrun stapler validate artifacts/*.dmg

# Windows
signtool verify /pa /all artifacts\*.exe
signtool verify /pa /all artifacts\*.msi

# Linux
dpkg-sig --verify artifacts/*.deb
gpg --verify artifacts/*.AppImage.asc artifacts/*.AppImage
```

Each artifact must have a matching `artifacts/sbom/<artifact>.cdx.json` with the
artifact SHA-256 recorded in the metadata component.

## Rollback and recall

Use rollback for a bad release that has not been broadly installed. Use recall
when the build is already installed or the signing identity may need distrust.

1. Freeze the release channel and stop automated promotion.
2. Remove the bad `.dmg`, `.exe`, `.msi`, `.deb`, and AppImage from download
   indexes. Keep immutable copies in the restricted incident archive.
3. Publish a signed known-bad-version manifest so launched clients show the
   in-app recall banner before starting a new capture.
4. macOS: delist the `.dmg`; if the binary is unsafe, revoke/notarization-block
   the ticket with Apple Developer support and publish the previous good `.dmg`.
5. Windows `.exe`: delist the installer and add the signer/build hash to the
   enterprise revocation list used by deployment tooling.
6. Windows `.msi`: publish a higher-versioned recall MSI that supersedes and
   uninstalls the bad ProductCode, then deploy the previous good MSI through
   GPO/SCCM.
7. Debian/Ubuntu: remove the `.deb` from the repository index, resign metadata,
   and publish a downgrade/epoch package only if automatic rollback is required.
8. AppImage: delist the binary and its detached signature; publish the previous
   good AppImage and SBOM pair.
9. Query opt-in crash telemetry and deployment-channel install logs to identify
   affected sites. Do not require telemetry to recall.
10. Preserve `%APPDATA%` / `~/Library/Application Support` / `~/.local/share`
    journal and audit-log directories during downgrade so evidence bundles are
    not lost.

Rollback rehearsal is complete only when staging has exercised all five artifact
families, including both Windows installer formats, and the previous good build
can open existing journals after downgrade.
