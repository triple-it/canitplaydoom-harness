# Can It Play DOOM? — Harness Specification

Status: Draft v0.1
Applies to: `canitplaydoom-harness`

This document defines the technical protocol between the harness, the game (ViZDoom), and the model — plus the result bundle format, scoring, and verification. It is the contract that makes runs comparable and replayable. See [PRD.md](PRD.md) for the product context.

---

## 1. Overview & goals

The harness is a neutral, deterministic runner. It:

- Runs **ViZDoom** in a pinned, seeded configuration.
- Presents the game state to a model in a chosen **modality**.
- Turns the model's decisions into game inputs.
- Records a **verifiable result bundle** (demo + logs + manifest + hash) and an mp4.

The participant supplies only the model/agent. The harness stays identical for everyone.

Design principle: the demo records the resulting **inputs per tic**, so replay is deterministic even though the model is not. Anyone can replay the demo and recompute the score.

---

## 2. Engine & environment

- Engine: **ViZDoom** (ZDoom-based), pinned in `requirements.txt`.
- Scenario config: shipped `.cfg` + `.wad` (e.g. `defend_the_center.cfg`), referenced by **SHA-256 hash** in the manifest.
- Determinism: fixed `--seed`; `doom_skill`, tic rate, and `frame_skip` pinned per benchmark.
- Recording: `DoomGame.new_episode(<demo_path>)` writes a ZDoom-format demo; `replay_episode(<demo_path>)` reproduces it.

Pinned defaults for v0.1 (`defend_the_center`):

| Setting | Value |
| --- | --- |
| `scenario` | `defend_the_center` |
| `available_buttons` | `TURN_LEFT`, `TURN_RIGHT`, `ATTACK` |
| `frame_skip` | 4 |
| `doom_skill` | 3 |
| `seed` | provided per run (recorded in manifest) |

---

## 3. Observation formats per modality

### 3.1 text-ASCII (v0.1)
A `rows x cols` character grid (default **32x64**, following DOOM-Mistral / SauerkrautLM) derived from ViZDoom buffers:

- Built from the **labels buffer** (object/enemy positions) and **screen/automap** geometry.
- Optional **depth buffer** summarized per column (nearest-obstacle distance bins).
- Each cell holds a single character from a fixed **legend**:

| Char | Meaning |
| --- | --- |
| `.` | empty / floor |
| `#` | wall |
| `Z` | enemy (e.g. Zombieman) |
| `I` | Imp / other monster |
| `+` | pickup / item |
| `^` | player facing marker (center column) |

The full legend is emitted in the manifest so it is self-describing. The grid + legend + a short instruction form the model prompt.

### 3.2 vision (future)
Raw RGB screenshot (pinned resolution) sent to a multimodal model. Same action interface.

### 3.3 tool-MCP (future)
Structured game state exposed as MCP resources + an action tool schema; the agent calls tools.

---

## 4. Action interface

- One action per decision step.
- Allowed actions for `defend_the_center`: `turn_left`, `turn_right`, `attack`.
- The model must return a single action as JSON: `{"action": "attack"}` (optionally `{"action": "attack", "reason": "..."}`).
- Parsing is lenient (first valid action token found). On parse failure or timeout, a **no-op** (or configured default) is applied and flagged in the log.
- Latency is measured per decision and recorded.

---

## 5. Agent adapter contract

A single **OpenAI-compatible** client covers both local and cloud models:

- **Local (Ollama):** base URL `http://localhost:11434/v1`, model e.g. `qwen2.5:14b-instruct`, no key.
- **Cloud (OpenRouter):** base URL `https://openrouter.ai/api/v1`, model e.g. `openai/gpt-4o-mini` / `anthropic/claude-3.5-sonnet` / etc., key from env `OPENROUTER_API_KEY`.

Adapter interface (conceptual):

```python
class Agent:
    def act(self, observation: str, legend: dict, allowed_actions: list[str]) -> Decision:
        # returns Decision(action, raw_response, latency_ms, prompt_tokens, completion_tokens)
        ...
```

CLI flags: `--model`, `--base-url`, `--api-key-env`, `--temperature`, `--max-steps`, `--max-tokens-per-step`.

---

## 6. Bundle format

A submission bundle is a directory (committed to `canitplaydoom-data`, kept tiny):

```
<bundle>/
  demo.lmp            # ViZDoom deterministic recording (authoritative proof)
  run_log.jsonl       # per-step game state
  llm_decisions.jsonl # per-step model I/O
  manifest.json       # metadata + scores + hashes
  run.mp4             # rendered video (uploaded to YouTube; not necessarily committed)
```

### `run_log.jsonl` (one JSON object per step)
```json
{"step": 0, "tic": 0, "action": "attack", "reward": 0.0, "health": 100, "ammo": 26, "kills": 0}
```

### `llm_decisions.jsonl` (one JSON object per step)
```json
{"step": 0, "prompt_sha": "…", "raw_response": "{\"action\":\"attack\"}", "action": "attack", "model": "qwen2.5:14b-instruct", "latency_ms": 812, "prompt_tokens": 2103, "completion_tokens": 12, "parse_ok": true}
```

### `manifest.json`
```json
{
  "schema_version": "0.1",
  "game": "doom",
  "engine": "vizdoom",
  "engine_version": "1.2.x",
  "scenario": "defend_the_center",
  "scenario_cfg_sha256": "…",
  "wad_sha256": "…",
  "seed": 12345,
  "modality": "ascii",
  "grid": {"rows": 32, "cols": 64, "legend": {".": "floor", "#": "wall", "Z": "enemy"}},
  "model": {"name": "qwen2.5:14b-instruct", "provider": "ollama", "params": null},
  "episodes": 5,
  "max_steps": 500,
  "scores": {"frags": 12, "survival_tics": 1840, "deaths": 1, "accuracy": 0.41, "composite": 148.4},
  "created_at": "2026-07-08T13:00:00Z",
  "bundle_sha256": "…"
}
```

The `bundle_sha256` is computed over the sorted contents of `demo.lmp`, `run_log.jsonl`, `llm_decisions.jsonl`, and the manifest body (excluding the hash field itself).

---

## 7. Scoring

### Per-benchmark metrics (v0.1 `defend_the_center`, per episode, averaged over episodes)
- **frags** — kills (`GameVariable.KILLCOUNT`).
- **survival_tics** — tics survived before death/episode end.
- **deaths** — deaths in the episode (0 or 1 for this single-life scenario).
- **accuracy** — `hits / shots`, where `shots` counts `attack` actions that consumed ammo and `hits` uses `GameVariable.HITCOUNT` when available (else `kills` as a proxy).

### Composite (scenario)
```
composite = frags * 10
          + (survival_tics / 35) * 1.0     # ~seconds
          - deaths * 5
          + accuracy * 20
```

Worked example: `frags=12`, `survival_tics=1840`, `deaths=1`, `accuracy=0.41`
```
= 12*10 + (1840/35)*1.0 - 1*5 + 0.41*20
= 120 + 52.57 - 5 + 8.2
= 175.77
```

(Weights are versioned via `schema_version`; the flagship E1M1 speedrun benchmark will define a time-primary composite.)

---

## 8. Verification

- **Replay:** `verify <bundle>` runs `replay_episode(demo.lmp)` in the pinned engine and recomputes `scores` from the replay.
- **Pass criteria:** recomputed scores match the manifest within a small tolerance; `scenario_cfg_sha256` / `wad_sha256` match the pinned assets; `bundle_sha256` is valid.
- **Consistency:** the number/order of actions in `llm_decisions.jsonl` and `run_log.jsonl` must correspond to the demo's inputs.
- This same command is the basis for Phase-2 automated CI re-verification.

---

## 9. Submission packaging

`package <bundle> --video-url <youtube>` produces the submission data file for a PR to `canitplaydoom-data`:

```
data/
  doom/
    defend_the_center/
      <model-slug>-<date>-<shortsha>/
        manifest.json
        run_log.jsonl
        llm_decisions.jsonl
        demo.lmp
        submission.json   # video URL, disclosure, author, links
```

`submission.json` (schema):
```json
{
  "schema_version": "0.1",
  "author": "github-username",
  "model": {"name": "qwen2.5:14b-instruct", "provider": "ollama", "modality": "ascii"},
  "benchmark": {"game": "doom", "scenario": "defend_the_center"},
  "video_url": "https://youtube.com/watch?v=…",
  "disclosure": {"prompts": "…", "setup": "…", "assistance": "none"},
  "bundle_sha256": "…"
}
```

CI on `canitplaydoom-data` validates the schema, the hashes, and (Phase 2) replays the demo.
