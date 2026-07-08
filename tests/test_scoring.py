from canitplaydoom.scoring import EpisodeMetrics, aggregate, composite_score


def test_composite_worked_example():
    # From HARNESS-SPEC.md §7.
    score = composite_score(frags=12, survival_tics=1840, deaths=1, accuracy=0.41)
    assert round(score, 2) == 175.77


def test_accuracy_zero_shots():
    m = EpisodeMetrics(frags=0, survival_tics=100, deaths=1, shots=0, hits=0)
    assert m.accuracy == 0.0


def test_accuracy_ratio():
    m = EpisodeMetrics(frags=3, survival_tics=100, deaths=0, shots=10, hits=4)
    assert m.accuracy == 0.4


def test_aggregate_empty():
    result = aggregate([])
    assert result["episodes"] == 0
    assert result["composite"] == 0.0


def test_aggregate_multiple_episodes():
    episodes = [
        EpisodeMetrics(frags=10, survival_tics=1000, deaths=1, shots=20, hits=10),
        EpisodeMetrics(frags=6, survival_tics=800, deaths=1, shots=10, hits=2),
    ]
    result = aggregate(episodes)
    assert result["episodes"] == 2
    assert result["frags"] == 8.0
    assert result["survival_tics"] == 900.0
    # accuracy is aggregated over totals: 12 hits / 30 shots
    assert result["accuracy"] == 0.4
