#!/usr/bin/env python3
"""Validate the Kiwi fork and emit release provenance/SBOM metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import sysconfig
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "KIWI_FORK.json"


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest() -> dict[str, object]:
    manifest = json.loads(MANIFEST_PATH.read_text())
    required = {
        "schemaVersion",
        "version",
        "upstreamRepository",
        "upstreamCommit",
        "pythonVersion",
        "rustToolchain",
        "license",
        "kiwiPatches",
    }
    missing = sorted(required.difference(manifest))
    if missing:
        raise SystemExit(f"KIWI_FORK.json missing fields: {', '.join(missing)}")
    return manifest


def validate(manifest: dict[str, object]) -> None:
    upstream = str(manifest["upstreamCommit"])
    subprocess.run(["git", "merge-base", "--is-ancestor", upstream, "HEAD"], cwd=ROOT,
                   check=True, stdout=subprocess.DEVNULL)
    pyproject = (ROOT / "pyproject.toml").read_text()
    expected = f'version = "{manifest["version"]}"'
    if expected not in pyproject:
        raise SystemExit(f"pyproject.toml does not contain {expected}")
    if str(manifest["license"]) != "LGPL-3.0-or-later":
        raise SystemExit("unexpected fork license")
    if not (ROOT / "LICENSE").exists():
        raise SystemExit("LICENSE is missing")
    patches = manifest["kiwiPatches"]
    if not isinstance(patches, list):
        raise SystemExit("kiwiPatches must be an array")
    patch_fields = {"id", "issue", "purpose", "adapterLimitation", "upstreamStatus", "tests"}
    for patch in patches:
        if not isinstance(patch, dict) or not patch_fields.issubset(patch):
            raise SystemExit("every Kiwi patch must contain governance evidence")
        if not str(patch["issue"]).startswith("https://github.com/"):
            raise SystemExit("every Kiwi patch must link to a GitHub issue")
        if not isinstance(patch["tests"], list) or not patch["tests"]:
            raise SystemExit("every Kiwi patch must declare tests")


def wheel_version(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        metadata_names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise SystemExit(f"expected one wheel METADATA, found {len(metadata_names)}")
        metadata = archive.read(metadata_names[0]).decode()
    for line in metadata.splitlines():
        if line.startswith("Version: "):
            return line.removeprefix("Version: ").strip()
    raise SystemExit("wheel version is missing")


def validate_wheel_notices(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        manifest_names = [name for name in names if name == "KIWI_FORK.json"]
        readme_names = [name for name in names if name == "KIWI_FORK.md"]
        embedded_manifest = archive.read(manifest_names[0]) if len(manifest_names) == 1 else b""
        embedded_readme = archive.read(readme_names[0]) if len(readme_names) == 1 else b""
    required_suffixes = ("KIWI_FORK.json", "KIWI_FORK.md", ".dist-info/licenses/LICENSE")
    missing = [suffix for suffix in required_suffixes if not any(
        name == suffix or name.endswith(suffix) for name in names
    )]
    if missing:
        raise SystemExit(f"wheel is missing release notices: {', '.join(missing)}")
    if embedded_manifest != MANIFEST_PATH.read_bytes():
        raise SystemExit("wheel fork manifest does not match the release source")
    if embedded_readme != (ROOT / "KIWI_FORK.md").read_bytes():
        raise SystemExit("wheel fork README does not match the release source")


def wheel_platform_tag(path: Path) -> str:
    parts = path.name.removesuffix(".whl").rsplit("-", 3)
    if len(parts) != 4:
        raise SystemExit(f"unexpected wheel filename: {path.name}")
    return parts[-1]


def emit(wheel: Path, output: Path, manifest: dict[str, object]) -> None:
    import tomllib

    expected_version = str(manifest["version"])
    actual_version = wheel_version(wheel)
    if actual_version != expected_version:
        raise SystemExit(f"wheel version {actual_version} != {expected_version}")
    validate_wheel_notices(wheel)
    expected_python = str(manifest["pythonVersion"])
    actual_python = f"{sys.version_info.major}.{sys.version_info.minor}"
    if actual_python != expected_python:
        raise SystemExit(f"build Python {actual_python} != {expected_python}")
    rust_version = subprocess.check_output(["rustc", "--version"], text=True).strip()
    if not rust_version.startswith(f'rustc {manifest["rustToolchain"]} '):
        raise SystemExit(f"unexpected Rust toolchain: {rust_version}")
    uv_version = subprocess.check_output(["uv", "--version"], text=True).strip()
    if not uv_version.startswith(f'uv {manifest["buildDependencies"]["uv"]}'):
        raise SystemExit(f"unexpected uv version: {uv_version}")
    compiler = os.environ.get("CC", "cc")
    compiler_version = subprocess.check_output(
        [compiler, "--version"], text=True, stderr=subprocess.STDOUT,
    ).splitlines()[0]
    provenance = {
        "schemaVersion": "kiwi-build-provenance-v1",
        "version": expected_version,
        "upstreamCommit": manifest["upstreamCommit"],
        "forkCommit": git("rev-parse", "HEAD"),
        "wheel": wheel.name,
        "wheelSha256": sha256(wheel),
        "dependencyLockHash": sha256(ROOT / "uv.lock"),
        "cargoLockHash": sha256(ROOT / "Cargo.lock"),
        "buildManifestHash": sha256(MANIFEST_PATH),
        "pythonVersion": manifest["pythonVersion"],
        "rustToolchain": manifest["rustToolchain"],
        "precisionMode": manifest["precisionMode"],
        "platform": wheel_platform_tag(wheel),
        "buildHostPlatform": sysconfig.get_platform(),
        "machine": platform.machine(),
        "hostOperatingSystem": platform.platform(),
        "pythonImplementation": platform.python_implementation(),
        "rustVersion": rust_version,
        "uvVersion": uv_version,
        "compilerVersion": compiler_version,
        "macosDeploymentTarget": os.environ.get("MACOSX_DEPLOYMENT_TARGET"),
        "runnerImage": os.environ.get("ImageOS"),
        "runnerImageVersion": os.environ.get("ImageVersion"),
        "sourceTreeDirty": bool(git("status", "--porcelain")),
        "license": manifest["license"],
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "kiwi-build-provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n"
    )
    (output / f"{wheel.name}.sha256").write_text(f'{provenance["wheelSha256"]}  {wheel.name}\n')
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    components = []
    for package in lock.get("package", []):
        name = str(package.get("name", ""))
        version = str(package.get("version", ""))
        if not name or not version or name == "nautilus-trader":
            continue
        component = {"type": "library", "name": name, "version": version}
        source = package.get("source", {})
        if isinstance(source, dict) and "registry" in source:
            component["purl"] = f"pkg:pypi/{name}@{version}"
        components.append(component)
    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "version": 1,
        "metadata": {"component": {
            "type": "library",
            "name": "nautilus_trader",
            "version": expected_version,
            "hashes": [{"alg": "SHA-256", "content": provenance["wheelSha256"]}],
            "licenses": [{"license": {"id": "LGPL-3.0-or-later"}}],
        }},
        "components": sorted(components, key=lambda item: (item["name"], item["version"])),
        "properties": [
            {"name": "kiwi:upstreamCommit", "value": str(manifest["upstreamCommit"])},
            {"name": "kiwi:forkCommit", "value": provenance["forkCommit"]},
            {"name": "kiwi:dependencyLockHash", "value": provenance["dependencyLockHash"]},
        ],
    }
    (output / "kiwi-sbom.cdx.json").write_text(
        json.dumps(sbom, indent=2, sort_keys=True) + "\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "kiwi-metadata")
    args = parser.parse_args()
    manifest = load_manifest()
    validate(manifest)
    if args.wheel:
        emit(args.wheel.resolve(), args.output.resolve(), manifest)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        print(f"git validation failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
