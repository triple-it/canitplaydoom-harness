"""Scoring for Can It Play DOOM? benchmarks.

Pure logic (no ViZDoom dependency) so it is unit-testable anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass

TICS_PER_SECOND = 35

# Composite weights (versioned via manifest schema_version).
W_FRAGS = 10.0
W_SURVIVAL_PER_SEC = 1.0
W_DEATH = 5.0
W_ACCURACY = 20.0


@dataclass
class EpisodeMetrics:
    """Raw metrics for a single episode of a scenario benchmark."""

    frags: int = 0
    survival_tics: int = 0
    deaths: int = 0
    shots: int = 0
    hits: int = 0

    @property
    def accuracy(self) -> float:
        return self.hits / self.shots if self.shots > 0 else 0.0


def composite_score(frags: float, survival_tics: float, deaths: float, accuracy: float) -> float:
    """Composite score for scenario-style benchmarks (see HARNESS-SPEC.md §7)."""
    return (
        frags * W_FRAGS
        + (survival_tics / TICS_PER_SECOND) * W_SURVIVAL_PER_SEC
        - deaths * W_DEATH
        + accuracy * W_ACCURACY
    )


def aggregate(episodes: list[EpisodeMetrics]) -> dict:
    """Average episode metrics and compute the composite score."""
    n = len(episodes)
    if n == 0:
        return {
            "frags": 0.0,
            "survival_tics": 0.0,
            "deaths": 0.0,
            "accuracy": 0.0,
            "composite": 0.0,
            "episodes": 0,
        }

    frags = sum(e.frags for e in episodes) / n
    survival = sum(e.survival_tics for e in episodes) / n
    deaths = sum(e.deaths for e in episodes) / n
    total_shots = sum(e.shots for e in episodes)
    total_hits = sum(e.hits for e in episodes)
    accuracy = total_hits / total_shots if total_shots > 0 else 0.0

    return {
        "frags": round(frags, 3),
        "survival_tics": round(survival, 1),
        "deaths": round(deaths, 3),
        "accuracy": round(accuracy, 4),
        "composite": round(composite_score(frags, survival, deaths, accuracy), 2),
        "episodes": n,
    }
