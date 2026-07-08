"""Package a verified bundle into a submission for canitplaydoom-data."""

from __future__ import annotations

import datetime as _dt
import json
import shutil
from pathlib import Path

from .bundle import read_manifest


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in text.lower()).strip("-")


def package_submission(
    bundle_dir: str,
    video_url: str,
    author: str,
    disclosure: dict | None = None,
    data_root: str = "data",
) -> Path:
    """Create the PR-ready submission directory under ``data_root``.

    Returns the created submission directory path.
    """
    bundle = Path(bundle_dir)
    manifest = read_manifest(bundle)

    model_name = manifest.get("model", {}).get("name", "unknown")
    date = _dt.date.today().isoformat()
    short = manifest.get("bundle_sha256", "000000")[:7]
    sub_name = f"{_slug(model_name)}-{date}-{short}"

    dest = Path(data_root) / manifest["game"] / manifest["scenario"] / sub_name
    dest.mkdir(parents=True, exist_ok=True)

    for name in ("manifest.json", "run_log.jsonl", "llm_decisions.jsonl"):
        src = bundle / name
        if src.exists():
            shutil.copy2(src, dest / name)
    for demo in bundle.glob("demo_*.lmp"):
        shutil.copy2(demo, dest / demo.name)

    submission = {
        "schema_version": "0.1",
        "author": author,
        "model": {
            "name": model_name,
            "provider": manifest.get("model", {}).get("provider"),
            "modality": manifest.get("modality"),
        },
        "benchmark": {"game": manifest["game"], "scenario": manifest["scenario"]},
        "video_url": video_url,
        "disclosure": disclosure or {"prompts": "", "setup": "", "assistance": "none"},
        "scores": manifest.get("scores", {}),
        "bundle_sha256": manifest.get("bundle_sha256"),
    }
    (dest / "submission.json").write_text(json.dumps(submission, indent=2, sort_keys=True))
    return dest
