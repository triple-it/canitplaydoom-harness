"""Benchmark/scenario configuration."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ScenarioConfig:
    name: str
    allowed_actions: list[str]
    frame_skip: int = 4
    doom_skill: int = 3


# v0.1 scenario. `allowed_actions` order matters: index 0 is the default/no-op fallback.
SCENARIOS: dict[str, ScenarioConfig] = {
    "defend_the_center": ScenarioConfig(
        name="defend_the_center",
        allowed_actions=["turn_left", "turn_right", "attack"],
        frame_skip=4,
        doom_skill=3,
    ),
}

# Maps our action names -> ViZDoom button names for each scenario.
ACTION_TO_BUTTON = {
    "turn_left": "TURN_LEFT",
    "turn_right": "TURN_RIGHT",
    "attack": "ATTACK",
}


def get_scenario(name: str) -> ScenarioConfig:
    if name not in SCENARIOS:
        raise ValueError(f"Unknown scenario '{name}'. Available: {list(SCENARIOS)}")
    return SCENARIOS[name]
