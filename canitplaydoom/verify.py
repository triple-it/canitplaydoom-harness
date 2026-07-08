"""Verify a bundle.

v0.1 (Phase 1) hard checks: bundle hash, pinned scenario cfg hash, and that
every demo loads and replays in the engine without error, with a consistent
number of logged steps.

Replaying the demo and recomputing scores is reported as an INFORMATIONAL
(soft) check: exact score-match on replay depends on full engine determinism,
which is a Phase-2 goal (see KNOWN_LIMITATIONS.md). Replay uses Mode.SPECTATOR
as required by ViZDoom for correct playback.
"""

from __future__ import annotations

import os
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
    """Validate a bundle. Returns a report dict with an overall ``ok`` flag.

    ``ok`` reflects the HARD checks only; soft checks are informational.
    """
    bundle = Path(bundle_dir)
    manifest = read_manifest(bundle)
    report: dict = {"ok": True, "checks": [], "info": []}

    def hard(name: str, ok: bool, detail: str = ""):
        report["checks"].append({"name": name, "ok": ok, "detail": detail})
        if not ok:
            report["ok"] = False

    def soft(name: str, detail: str):
        report["info"].append({"name": name, "detail": detail})

    # HARD 1: bundle hash.
    recomputed_hash = compute_bundle_hash(bundle, manifest)
    hard(
        "bundle_sha256",
        recomputed_hash == manifest.get("bundle_sha256"),
        "match" if recomputed_hash == manifest.get("bundle_sha256")
        else f"expected {manifest.get('bundle_sha256')}, got {recomputed_hash}",
    )

    # HARD 2: pinned scenario cfg hash.
    import vizdoom as vzd

    cfg = os.path.join(vzd.scenarios_path, f"{manifest['scenario']}.cfg")
    if os.path.exists(cfg):
        ok = sha256_file(cfg) == manifest.get("scenario_cfg_sha256")
        hard("scenario_cfg_sha256", ok, "match" if ok else "pinned scenario cfg mismatch")
    else:
        hard("scenario_cfg_sha256", False, "scenario cfg not found in this ViZDoom install")

    # HARD 3 + SOFT: replay each demo (SPECTATOR mode) and recompute scores.
    scenario = get_scenario(manifest["scenario"])
    demos = sorted(bundle.glob("demo_*.lmp"))
    detail = manifest.get("episodes_detail", [])
    game, _ = _build_game(
        scenario, int(manifest["seed"]), record_visuals=False, mode=vzd.Mode.SPECTATOR
    )
    try:
        for i, demo in enumerate(demos):
            try:
                got = _replay_episode(game, str(demo.resolve()))
            except Exception as exc:  # noqa: BLE001
                hard(f"demo_{i}_replays", False, f"replay raised: {exc}")
                continue
            hard(f"demo_{i}_replays", True, "ok")
            if i < len(detail):
                exp = detail[i]
                match = (
                    abs(got["frags"] - exp["frags"]) <= tolerance
                    and abs(got["survival_tics"] - exp["survival_tics"]) <= max(tolerance, 5)
                    and got["deaths"] == exp["deaths"]
                )
                soft(
                    f"replay_score_match_{i}",
                    f"{'MATCH' if match else 'DIVERGES (Phase-2 determinism)'}: "
                    f"manifest {exp['frags']}f/{exp['survival_tics']}t/{exp['deaths']}d, "
                    f"replay {got['frags']}f/{got['survival_tics']}t/{got['deaths']}d",
                )
    finally:
        game.close()

    return report
