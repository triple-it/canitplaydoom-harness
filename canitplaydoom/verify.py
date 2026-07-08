"""Verify a bundle by replaying its demo(s) and recomputing scores."""

from __future__ import annotations

from pathlib import Path

from .bundle import compute_bundle_hash, read_manifest, sha256_file
from .config import get_scenario
from .runner import _build_game, _safe_get_var


def _replay_episode(game, demo_path: str) -> dict:
    game.replay_episode(demo_path)
    while not game.is_episode_finished():
        game.advance_action()
    return {
        "frags": int(_safe_get_var(game, "KILLCOUNT") or 0),
        "survival_tics": int(game.get_episode_time()),
        "deaths": 1 if game.is_player_dead() else 0,
    }


def verify_bundle(bundle_dir: str, tolerance: float = 1.0) -> dict:
    """Replay demos, recompute deterministic scores, and validate hashes.

    Returns a report dict with an overall ``ok`` flag.
    """
    bundle = Path(bundle_dir)
    manifest = read_manifest(bundle)
    report: dict = {"ok": True, "checks": []}

    def check(name: str, ok: bool, detail: str = ""):
        report["checks"].append({"name": name, "ok": ok, "detail": detail})
        if not ok:
            report["ok"] = False

    # 1) Bundle hash.
    recomputed_hash = compute_bundle_hash(bundle, manifest)
    check("bundle_sha256", recomputed_hash == manifest.get("bundle_sha256"),
          f"expected {manifest.get('bundle_sha256')}, got {recomputed_hash}")

    # 2) Scenario cfg hash (pinned asset).
    import vizdoom as vzd
    import os

    cfg = os.path.join(vzd.scenarios_path, f"{manifest['scenario']}.cfg")
    if os.path.exists(cfg):
        check("scenario_cfg_sha256", sha256_file(cfg) == manifest.get("scenario_cfg_sha256"),
              "pinned scenario cfg mismatch")
    else:
        check("scenario_cfg_sha256", False, "scenario cfg not found in this ViZDoom install")

    # 3) Replay each demo and compare to per-episode detail.
    scenario = get_scenario(manifest["scenario"])
    demos = sorted(bundle.glob("demo_*.lmp"))
    detail = manifest.get("episodes_detail", [])
    game, _ = _build_game(scenario, int(manifest["seed"]), record_visuals=False)
    try:
        for i, demo in enumerate(demos):
            got = _replay_episode(game, str(demo.resolve()))
            if i < len(detail):
                exp = detail[i]
                ok = (
                    abs(got["frags"] - exp["frags"]) <= tolerance
                    and abs(got["survival_tics"] - exp["survival_tics"]) <= max(tolerance, 2)
                    and got["deaths"] == exp["deaths"]
                )
                check(f"replay_episode_{i}", ok, f"expected {exp}, replay {got}")
            else:
                check(f"replay_episode_{i}", True, f"replay {got} (no stored detail)")
    finally:
        game.close()

    return report
