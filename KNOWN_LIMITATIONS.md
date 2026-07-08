# Known limitations (v0.1)

## Exact demo-replay determinism (Phase-2)

ViZDoom `.lmp` demos are the authoritative record of a run. In v0.1, `verify`
checks:

- the bundle content hash,
- the pinned scenario `.cfg` hash,
- that every demo **loads and replays** in the engine without error.

Recomputing the score from the replay and requiring an **exact match** is an
INFORMATIONAL (soft) check in v0.1. We observed that a fixed action sequence,
recorded and replayed (in `Mode.SPECTATOR`, with the recording finalized via a
trailing `new_episode()`), can still diverge slightly in outcome on this
engine/platform. This is a known ViZDoom determinism area (see upstream work on
resetting animated textures and audio, ViZDoom PRs #672 / #673).

Consequently, per the [PRD](PRD.md):

- **Phase 1 (v0.1) verification** = hash + schema + demo-replays-without-error,
  plus manual/community review of the bundle and the required video.
- **Phase 2 verification** = automated strict replay + score recompute. This
  requires pinning a ViZDoom build with full deterministic replay (and likely
  disabling animated textures/audio in the scenario). Tracked as a Phase-2 task.

The demo remains valuable now: it can be replayed visually to inspect the run,
and it is the artifact Phase-2 automated re-verification will consume.
