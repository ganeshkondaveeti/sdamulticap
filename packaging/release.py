#!/usr/bin/env python3
"""Phase 10 release builder for MultiCap.

Builds the PyInstaller one-folder bundle, smokes the bundled executable, wraps it
in the host OS artifact, signs when release credentials are present, and emits a
CycloneDX SBOM for each produced artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
ARTIFACTS = ROOT / "artifacts"
SBOM_DIR = ARTIFACTS / "sbom"
PYINSTALLER_SPEC = ROOT / "packaging" / "pyinstaller" / "multicap.spec"
APP_NAME = "multicap"
Target = Literal["auto", "macos", "windows", "linux"]
TARGETS: tuple[Target, ...] = ("auto", "macos", "windows", "linux")


@dataclass(frozen=True)
class ReleaseArgs:
    target: Target
    unsigned_local: bool
    clean: bool


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    version = read_version()
    if args.clean:
        clean()

    bundle = build_pyinstaller()
    smoke_bundle(bundle)
    produced: list[Path] = [bundle]

    if args.target in {"auto", "macos"} and sys.platform == "darwin":
        produced.append(build_macos_dmg(version, sign=not args.unsigned_local))
    elif args.target == "macos":
        raise SystemExit("macOS .dmg builds must run on macOS")

    if args.target in {"auto", "windows"} and sys.platform == "win32":
        produced.extend(build_windows_installers(version, sign=not args.unsigned_local))
    elif args.target == "windows":
        raise SystemExit("Windows .exe/.msi builds must run on Windows")

    if args.target in {"auto", "linux"} and sys.platform.startswith("linux"):
        produced.extend(build_linux_artifacts(version, sign=not args.unsigned_local))
    elif args.target == "linux":
        raise SystemExit("Linux .deb/AppImage builds must run on Linux")

    for artifact in produced:
        _ = write_artifact_sbom(artifact, version)

    print("Phase 10 artifacts:")
    for artifact in produced:
        print(f"  {artifact.relative_to(ROOT)}")
    return 0


def parse_args(argv: Sequence[str] | None) -> ReleaseArgs:
    parser = argparse.ArgumentParser(description="Build Phase 10 release artifacts")
    _ = parser.add_argument(
        "--target",
        choices=("auto", "macos", "windows", "linux"),
        default="auto",
        help="host OS artifact family to build after PyInstaller",
    )
    _ = parser.add_argument(
        "--unsigned-local",
        action="store_true",
        help="allow local unsigned artifacts when signing credentials/tools are unavailable",
    )
    _ = parser.add_argument("--clean", action="store_true", help="remove build output first")
    parsed = cast(dict[str, object], vars(parser.parse_args(argv)))
    target = str(parsed["target"])
    if target not in TARGETS:
        raise SystemExit(f"Unsupported target: {target}")
    return ReleaseArgs(
        target=target,
        unsigned_local=bool(parsed["unsigned_local"]),
        clean=bool(parsed["clean"]),
    )


def clean() -> None:
    for path in (ROOT / "build", DIST, ARTIFACTS):
        if path.exists():
            shutil.rmtree(path)


def read_version() -> str:
    in_project = False
    for raw_line in (ROOT / "pyproject.toml").read_text().splitlines():
        line = raw_line.strip()
        if line == "[project]":
            in_project = True
            continue
        if in_project and line.startswith("["):
            break
        if in_project and line.startswith("version"):
            return line.split("=", maxsplit=1)[1].split("#", maxsplit=1)[0].strip().strip('"')
    raise SystemExit("project.version is missing from pyproject.toml")


def build_pyinstaller() -> Path:
    _ = run(
        [
            "uv",
            "run",
            "--with",
            "pyinstaller",
            "pyinstaller",
            str(PYINSTALLER_SPEC),
            "--noconfirm",
        ]
    )
    if sys.platform == "darwin":
        bundle = DIST / "MultiCap.app"
    else:
        bundle = DIST / APP_NAME
    require_exists(bundle)
    return bundle


def smoke_bundle(bundle: Path) -> None:
    if sys.platform == "darwin" and bundle.suffix == ".app":
        executable = bundle / "Contents" / "MacOS" / APP_NAME
    elif sys.platform == "win32":
        executable = bundle / "multicap.exe"
    else:
        executable = bundle / "multicap"
    require_exists(executable)
    env = os.environ.copy()
    _ = env.setdefault("QT_QPA_PLATFORM", "offscreen")
    completed = run([str(executable), "--smoke"], env=env, capture=True)
    output = completed.stdout + completed.stderr
    if "multicap GUI smoke ok" not in output:
        raise SystemExit(f"Bundled smoke did not report success:\n{output}")


def build_macos_dmg(version: str, *, sign: bool) -> Path:
    app = DIST / "MultiCap.app"
    dmg = ARTIFACTS / f"multicap-{version}-macos-universal.dmg"
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    require_exists(app)
    if sign:
        require_env("SIGNING_IDENTITY")
        _ = run(
            [
                "codesign",
                "--force",
                "--deep",
                "--options",
                "runtime",
                "--entitlements",
                str(ROOT / "packaging" / "macos" / "entitlements.plist"),
                "--sign",
                os.environ["SIGNING_IDENTITY"],
                "--timestamp",
                str(app),
            ]
        )
        _ = run(["codesign", "--verify", "--deep", "--strict", "--verbose=2", str(app)])
    if dmg.exists():
        dmg.unlink()
    _ = run(
        [
            "hdiutil",
            "create",
            "-volname",
            "MultiCap",
            "-srcfolder",
            str(app),
            "-ov",
            "-format",
            "UDZO",
            str(dmg),
        ]
    )
    if sign:
        _ = run(
            [
                "codesign",
                "--force",
                "--sign",
                os.environ["SIGNING_IDENTITY"],
                "--timestamp",
                str(dmg),
            ]
        )
        notarize_and_staple(dmg)
    return dmg


def notarize_and_staple(dmg: Path) -> None:
    require_env("APPLE_ID")
    require_env("APPLE_TEAM_ID")
    require_env("APPLE_APP_PASSWORD")
    _ = run(
        [
            "xcrun",
            "notarytool",
            "submit",
            str(dmg),
            "--apple-id",
            os.environ["APPLE_ID"],
            "--team-id",
            os.environ["APPLE_TEAM_ID"],
            "--password",
            os.environ["APPLE_APP_PASSWORD"],
            "--wait",
        ]
    )
    _ = run(["xcrun", "stapler", "staple", str(dmg)])
    _ = run(["xcrun", "stapler", "validate", str(dmg)])


def build_windows_installers(version: str, *, sign: bool) -> list[Path]:
    bundle = DIST / APP_NAME
    embedded_exe = bundle / "multicap.exe"
    require_exists(embedded_exe)
    if sign:
        sign_windows(embedded_exe)

    inno = which("iscc")
    heat = which("heat")
    candle = which("candle")
    light = which("light")
    if inno is None or heat is None or candle is None or light is None:
        raise SystemExit(
            "Install Inno Setup and WiX Toolset before building Windows release artifacts"
        )

    _ = run([inno, f"/DAppVersion={version}", str(ROOT / "packaging" / "windows" / "multicap.iss")])
    setup = first_existing((ROOT / "packaging" / "windows" / "Output").glob("*.exe"))

    components = ROOT / "packaging" / "windows" / "components.wxs"
    _ = run(
        [
            heat,
            "dir",
            str(bundle),
            "-cg",
            "MulticapComponents",
            "-arch",
            "x64",
            "-gg",
            "-sfrag",
            "-srd",
            "-sreg",
            "-suid",
            "-var",
            "var.SourceDir",
            "-dr",
            "INSTALLFOLDER",
            "-out",
            str(components),
        ]
    )
    _ = run(
        [
            candle,
            str(ROOT / "packaging" / "windows" / "multicap.wxs"),
            str(components),
            "-arch",
            "x64",
            f"-dSourceDir={bundle}",
            f"-dProductVersion={version}",
            "-out",
            str(ROOT / "packaging" / "windows") + os.sep,
        ]
    )
    msi = ARTIFACTS / f"multicap-{version}-windows-x64.msi"
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    _ = run(
        [
            light,
            str(ROOT / "packaging" / "windows" / "multicap.wixobj"),
            str(ROOT / "packaging" / "windows" / "components.wixobj"),
            "-out",
            str(msi),
        ]
    )
    setup_artifact = ARTIFACTS / f"multicap-{version}-windows-x64-setup.exe"
    _ = shutil.copy2(setup, setup_artifact)
    if sign:
        sign_windows(setup_artifact)
        sign_windows(msi)
    return [setup_artifact, msi]


def sign_windows(path: Path) -> None:
    require_env("WINDOWS_CERT_PATH")
    require_env("WINDOWS_CERT_PASSWORD")
    signtool = which("signtool")
    if signtool is None:
        raise SystemExit("signtool is required for signed Windows release artifacts")
    _ = run(
        [
            signtool,
            "sign",
            "/fd",
            "SHA256",
            "/td",
            "SHA256",
            "/tr",
            os.environ.get("WINDOWS_TIMESTAMP_URL", "http://timestamp.digicert.com"),
            "/f",
            os.environ["WINDOWS_CERT_PATH"],
            "/p",
            os.environ["WINDOWS_CERT_PASSWORD"],
            str(path),
        ]
    )


def build_linux_artifacts(version: str, *, sign: bool) -> list[Path]:
    bundle = DIST / APP_NAME
    require_exists(bundle)
    deb = build_deb(bundle, version, sign=sign)
    appimage = build_appimage(bundle, version, sign=sign)
    return [deb, appimage]


def build_deb(bundle: Path, version: str, *, sign: bool) -> Path:
    pkgroot = ROOT / "build" / "deb" / "multicap"
    if pkgroot.exists():
        shutil.rmtree(pkgroot)
    appdir = pkgroot / "opt" / "multicap"
    bindir = pkgroot / "usr" / "bin"
    applications = pkgroot / "usr" / "share" / "applications"
    appdir.mkdir(parents=True)
    bindir.mkdir(parents=True)
    applications.mkdir(parents=True)
    copy_tree(bundle, appdir)
    (bindir / "multicap").symlink_to("/opt/multicap/multicap")
    _ = shutil.copy2(
        ROOT / "packaging" / "linux" / "appimage" / "multicap.desktop",
        applications / "multicap.desktop",
    )
    debian = pkgroot / "DEBIAN"
    debian.mkdir()
    control = (ROOT / "packaging" / "linux" / "deb" / "DEBIAN" / "control").read_text()
    _ = (debian / "control").write_text(control.replace("Version: 0.0.0", f"Version: {version}"))
    deb = ARTIFACTS / f"multicap_{version}_amd64.deb"
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    _ = run(["dpkg-deb", "--build", str(pkgroot), str(deb)])
    if sign:
        require_env("DPKG_SIG_KEY_ID")
        dpkg_sig = which("dpkg-sig")
        if dpkg_sig is None:
            raise SystemExit("dpkg-sig is required for signed Debian release artifacts")
        _ = run([dpkg_sig, "--sign", "builder", "-k", os.environ["DPKG_SIG_KEY_ID"], str(deb)])
    return deb


def build_appimage(bundle: Path, version: str, *, sign: bool) -> Path:
    appdir = ROOT / "build" / "appimage" / "MultiCap.AppDir"
    if appdir.exists():
        shutil.rmtree(appdir)
    usr_bin = appdir / "usr" / "bin"
    usr_bin.mkdir(parents=True)
    copy_tree(bundle, usr_bin)
    _ = shutil.copy2(ROOT / "packaging" / "linux" / "appimage" / "AppRun", appdir / "AppRun")
    _ = shutil.copy2(
        ROOT / "packaging" / "linux" / "appimage" / "multicap.desktop",
        appdir / "multicap.desktop",
    )
    _ = (appdir / "multicap.png").write_bytes(base_png())
    appimagetool = which("appimagetool")
    if appimagetool is None:
        raise SystemExit("appimagetool is required for Linux AppImage release artifacts")
    appimage = ARTIFACTS / f"MultiCap-{version}-x86_64.AppImage"
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["ARCH"] = "x86_64"
    _ = run([appimagetool, str(appdir), str(appimage)], env=env)
    if sign:
        require_env("GPG_SIGNING_KEY_ID")
        _ = run(
            [
                "gpg",
                "--batch",
                "--yes",
                "--detach-sign",
                "--armor",
                "--local-user",
                os.environ["GPG_SIGNING_KEY_ID"],
                str(appimage),
            ]
        )
    return appimage


def write_artifact_sbom(artifact: Path, version: str) -> Path:
    SBOM_DIR.mkdir(parents=True, exist_ok=True)
    digest = digest_path(artifact)
    bom = {
        "$schema": "http://cyclonedx.org/schema/bom-1.6.schema.json",
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, artifact.name + digest)}",
        "version": 1,
        "metadata": {
            "timestamp": "1970-01-01T00:00:00+00:00",
            "component": {
                "type": "application",
                "name": "multicap",
                "version": version,
                "bom-ref": f"multicap@{version}:{artifact.name}",
                "hashes": [{"alg": "SHA-256", "content": digest}],
                "properties": [
                    {"name": "multicap:artifact", "value": artifact.name},
                    {"name": "multicap:platform", "value": platform.platform()},
                ],
            },
        },
        "components": dependency_components(),
    }
    out = SBOM_DIR / f"{artifact.name}.cdx.json"
    _ = out.write_text(json.dumps(bom, indent=2, sort_keys=True) + "\n")
    return out


def dependency_components() -> list[dict[str, object]]:
    components: list[dict[str, object]] = []
    name = ""
    version = ""
    for raw_line in (ROOT / "uv.lock").read_text().splitlines():
        line = raw_line.strip()
        if line == "[[package]]":
            if name and version:
                components.append(component(name, version))
            name = ""
            version = ""
        elif line.startswith("name = "):
            name = line.split("=", maxsplit=1)[1].strip().strip('"')
        elif line.startswith("version = "):
            version = line.split("=", maxsplit=1)[1].strip().strip('"')
    if name and version:
        components.append(component(name, version))
    return sorted(components, key=lambda item: str(item["name"]).lower())


def component(name: str, version: str) -> dict[str, object]:
    return {
        "type": "library",
        "name": name,
        "version": version,
        "bom-ref": f"{name}=={version}",
        "purl": f"pkg:pypi/{name}@{version}",
    }


def digest_path(path: Path) -> str:
    hasher = hashlib.sha256()
    if path.is_dir():
        for file in sorted(item for item in path.rglob("*") if item.is_file()):
            hasher.update(str(file.relative_to(path)).encode())
            hasher.update(file.read_bytes())
    else:
        hasher.update(path.read_bytes())
    return hasher.hexdigest()


def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    _ = shutil.copytree(src, dst, symlinks=True)


def require_exists(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"Required path does not exist: {path}")


def require_env(name: str) -> None:
    if not os.environ.get(name):
        raise SystemExit(
            f"{name} is required for signed release artifacts; use --unsigned-local for smoke builds"
        )


def first_existing(paths: Iterable[Path]) -> Path:
    for path in paths:
        if path.exists():
            return path
    raise SystemExit("Expected artifact was not produced")


def which(name: str) -> str | None:
    return shutil.which(name)


def run(
    args: Sequence[str], *, env: dict[str, str] | None = None, capture: bool = False
) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(args))
    return subprocess.run(
        args,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=capture,
        check=True,
    )


def base_png() -> bytes:
    encoded = (
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000a49444154789c63600000020001527d0a2d0000000049454e44ae426082"
    )
    return bytes.fromhex(encoded)


if __name__ == "__main__":
    raise SystemExit(main())
