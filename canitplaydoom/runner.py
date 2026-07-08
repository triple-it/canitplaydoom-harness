"""Benchmark runner: drives ViZDoom with a model and writes a result bundle.

ViZDoom is imported lazily so the rest of the package (scoring, encoding,
agent, bundle) can be used/tested without the engine installed.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
from pathlib import Path

from . import __version__
from .ascii_encoder import LEGEND, LabelInfo, encode
from .bundle import sha256_file, write_manifest
from .config import ACTION_TO_BUTTON, get_scenario
from .scoring import EpisodeMetrics, aggregate


def _safe_get_var(game, name):
    """Return a GameVariable value if the enum exists in this ViZDoom build."""
    import vizdoom as vzd

    var = getattr(vzd.GameVariable, name, None)
    if var is None:
        return None
    try:
        return game.get_game_variable(var)
    except Exception:  # noqa: BLE001
        return None


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_game(scenario, seed: int, record_visuals: bool, mode=None):
    import vizdoom as vzd

    game = vzd.DoomGame()
    cfg = os.path.join(vzd.scenarios_path, f"{scenario.name}.cfg")
    game.load_config(cfg)
    game.set_labels_buffer_enabled(True)
    game.set_depth_buffer_enabled(True)
    if record_visuals:
        game.set_screen_format(vzd.ScreenFormat.RGB24)
    game.set_window_visible(False)
    game.set_mode(mode if mode is not None else vzd.Mode.PLAYER)
    game.set_seed(seed)
    for extra in ("KILLCOUNT", "HITCOUNT", "HEALTH", "AMMO2"):
        var = getattr(vzd.GameVariable, extra, None)
        if var is not None:
            game.add_available_game_variable(var)
    game.init()
    return game, os.path.abspath(cfg)


def _action_vectors(game, allowed_actions):
    """Map our action names to one-hot ViZDoom button vectors."""
    buttons = game.get_available_buttons()
    button_names = [b.name for b in buttons]
    vectors = {}
    for action in allowed_actions:
        vec = [0] * len(buttons)
        btn = ACTION_TO_BUTTON.get(action)
        if btn in button_names:
            vec[button_names.index(btn)] = 1
        vectors[action] = vec
    return vectors


def run_benchmark(
    scenario_name: str,
    agent,
    episodes: int,
    max_steps: int,
    seed: int,
    out_dir: str,
    model_meta: dict,
    modality: str = "ascii",
    render_video: bool = True,
    grid_rows: int = 32,
    grid_cols: int = 64,
) -> dict:
    """Run the benchmark and write a bundle to ``out_dir``. Returns the manifest."""
    scenario = get_scenario(scenario_name)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    game, cfg_path = _build_game(scenario, seed, record_visuals=render_video)
    action_vectors = _action_vectors(game, scenario.allowed_actions)

    run_log = open(out / "run_log.jsonl", "w")
    dec_log = open(out / "llm_decisions.jsonl", "w")
    frames = []
    episode_metrics: list[EpisodeMetrics] = []
    step_counter = 0

    try:
        for ep in range(episodes):
            demo_path = str((out / f"demo_{ep:03d}.lmp").resolve())
            game.new_episode(demo_path)

            prev_ammo = _safe_get_var(game, "AMMO2")
            prev_hits = _safe_get_var(game, "HITCOUNT") or 0
            shots = hits = 0

            for _ in range(max_steps):
                if game.is_episode_finished():
                    break
                state = game.get_state()
                if state is None:
                    break

                labels = [LabelInfo(l.value, l.object_name) for l in state.labels]
                obs = encode(state.labels_buffer, labels, state.depth_buffer,
                             rows=grid_rows, cols=grid_cols)
                decision = agent.act(obs, LEGEND, scenario.allowed_actions)

                if render_video and state.screen_buffer is not None:
                    frames.append(state.screen_buffer)

                game.make_action(action_vectors[decision.action], scenario.frame_skip)

                cur_ammo = _safe_get_var(game, "AMMO2")
                if decision.action == "attack" and prev_ammo is not None and cur_ammo is not None:
                    if cur_ammo < prev_ammo:
                        shots += 1
                prev_ammo = cur_ammo

                cur_hits = _safe_get_var(game, "HITCOUNT")
                if cur_hits is not None:
                    hits = int(cur_hits)

                kills = _safe_get_var(game, "KILLCOUNT") or 0
                run_log.write(json.dumps({
                    "step": step_counter,
                    "episode": ep,
                    "tic": game.get_episode_time(),
                    "action": decision.action,
                    "health": _safe_get_var(game, "HEALTH"),
                    "ammo": cur_ammo,
                    "kills": int(kills),
                }) + "\n")
                dec_log.write(json.dumps({
                    "step": step_counter,
                    "episode": ep,
                    "raw_response": decision.raw_response,
                    "action": decision.action,
                    "model": agent.model,
                    "latency_ms": decision.latency_ms,
                    "prompt_tokens": decision.prompt_tokens,
                    "completion_tokens": decision.completion_tokens,
                    "parse_ok": decision.parse_ok,
                }) + "\n")
                step_counter += 1

            frags = int(_safe_get_var(game, "KILLCOUNT") or 0)
            survival = game.get_episode_time()
            dead = game.is_player_dead()
            if hits == 0:
                hits = frags  # proxy when HITCOUNT unavailable
            episode_metrics.append(EpisodeMetrics(
                frags=frags,
                survival_tics=int(survival),
                deaths=1 if dead else 0,
                shots=shots,
                hits=hits,
            ))
        # A trailing new_episode() is required to stop and flush the last
        # recording to disk before closing (see ViZDoom record_episodes example).
        game.new_episode()
    finally:
        run_log.close()
        dec_log.close()
        game.close()

    if render_video and frames:
        _write_video(out / "run.mp4", frames)

    scores = aggregate(episode_metrics)
    manifest = {
        "schema_version": "0.1",
        "harness_version": __version__,
        "game": "doom",
        "engine": "vizdoom",
        "engine_version": _vizdoom_version(),
        "scenario": scenario.name,
        "scenario_cfg_sha256": sha256_file(cfg_path),
        "seed": seed,
        "modality": modality,
        "grid": {"rows": grid_rows, "cols": grid_cols, "legend": LEGEND},
        "model": model_meta,
        "episodes": episodes,
        "max_steps": max_steps,
        "scores": scores,
        "episodes_detail": [
            {
                "frags": m.frags,
                "survival_tics": m.survival_tics,
                "deaths": m.deaths,
                "shots": m.shots,
                "hits": m.hits,
                "accuracy": round(m.accuracy, 4),
            }
            for m in episode_metrics
        ],
        "created_at": _now_iso(),
    }
    write_manifest(out, manifest)
    return manifest


def _vizdoom_version() -> str:
    try:
        import vizdoom as vzd

        return getattr(vzd, "__version__", "unknown")
    except Exception:  # noqa: BLE001
        return "unknown"


def _write_video(path, frames, fps: int = 35):
    try:
        import cv2
        import numpy as np
    except ImportError:
        return
    if not frames:
        return
    first = np.asarray(frames[0])
    # ViZDoom RGB24 comes as (H, W, 3); ensure shape.
    if first.ndim == 3 and first.shape[0] == 3:
        frames = [np.transpose(np.asarray(f), (1, 2, 0)) for f in frames]
        first = frames[0]
    h, w = first.shape[:2]
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for f in frames:
        arr = np.asarray(f)
        writer.write(cv2.cvtColor(arr, cv2.COLOR_RGB2BGR))
    writer.release()
