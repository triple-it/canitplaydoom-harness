"""Result-bundle helpers: file hashing and manifest hashing."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

# Files excluded from the bundle hash (derived/optional artifacts).
_HASH_EXCLUDE = {"manifest.json"}
_HASH_EXCLUDE_SUFFIXES = {".mp4"}


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compute_bundle_hash(bundle_dir: str | Path, manifest: dict) -> str:
    """Hash all core bundle files + the manifest body (excluding bundle_sha256).

    Includes demo(s) and the jsonl logs; excludes the manifest and video.
    """
    bundle_dir = Path(bundle_dir)
    h = hashlib.sha256()
    files = sorted(
        p
        for p in bundle_dir.iterdir()
        if p.is_file()
        and p.name not in _HASH_EXCLUDE
        and p.suffix not in _HASH_EXCLUDE_SUFFIXES
    )
    for fp in files:
        h.update(fp.name.encode())
        h.update(sha256_file(fp).encode())
    manifest_body = {k: v for k, v in manifest.items() if k != "bundle_sha256"}
    h.update(json.dumps(manifest_body, sort_keys=True).encode())
    return h.hexdigest()


def write_manifest(bundle_dir: str | Path, manifest: dict) -> str:
    bundle_dir = Path(bundle_dir)
    manifest = dict(manifest)
    manifest["bundle_sha256"] = compute_bundle_hash(bundle_dir, manifest)
    (bundle_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return manifest["bundle_sha256"]


def read_manifest(bundle_dir: str | Path) -> dict:
    return json.loads((Path(bundle_dir) / "manifest.json").read_text())
