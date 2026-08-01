import pandas as pd

from soccer_intelligence.game_state import add_game_state
from soccer_intelligence.metrics import aggregate_player_metrics


def test_game_state_is_assigned_before_a_goal_changes_the_score() -> None:
    events = pd.DataFrame(
        [
            {"index": 1, "team.id": 10, "type.name": "Pass", "period": 1},
            {
                "index": 2,
                "team.id": 20,
                "type.name": "Shot",
                "shot.outcome.name": "Goal",
                "period": 1,
            },
            {"index": 3, "team.id": 20, "type.name": "Pass", "period": 1},
            {"index": 4, "team.id": 10, "type.name": "Pass", "period": 1},
        ]
    )

    result = add_game_state(events, home_team_id=10, away_team_id=20)

    assert result["game_state"].tolist() == ["drawing", "drawing", "leading", "trailing"]
    assert result["home_score_before"].tolist() == [0, 0, 0, 0]
    assert result["away_score_before"].tolist() == [0, 0, 1, 1]


def test_penalty_shootout_goal_does_not_change_match_state() -> None:
    events = pd.DataFrame(
        [
            {
                "index": 1,
                "team.id": 10,
                "type.name": "Shot",
                "shot.outcome.name": "Goal",
                "period": 5,
            },
            {"index": 2, "team.id": 20, "type.name": "Pass", "period": 5},
        ]
    )

    result = add_game_state(events, home_team_id=10, away_team_id=20)

    assert result["game_state"].tolist() == ["drawing", "drawing"]


def test_own_goal_is_credited_to_the_opponent() -> None:
    events = pd.DataFrame(
        [
            {
                "index": 1,
                "team.id": 10,
                "type.name": "Own Goal Against",
                "period": 1,
            },
            {"index": 2, "team.id": 20, "type.name": "Pass", "period": 1},
            {"index": 3, "team.id": 10, "type.name": "Pass", "period": 1},
        ]
    )

    result = add_game_state(events, home_team_id=10, away_team_id=20)

    assert result["game_state"].tolist() == ["drawing", "leading", "trailing"]
    assert result["away_score_before"].tolist() == [0, 1, 1]


def test_season_aggregation_sums_actions_and_counts_matches() -> None:
    match_rows = pd.DataFrame(
        [
            {
                "match_id": 1,
                "team.name": "A",
                "player.name": "Player",
                "game_state": "trailing",
                "events": 8,
                "passes": 4,
                "progressive_passes": 2,
                "completed_progressive_passes": 1,
                "progressive_distance": 25.0,
                "shots": 1,
                "xg": 0.2,
            },
            {
                "match_id": 2,
                "team.name": "A",
                "player.name": "Player",
                "game_state": "trailing",
                "events": 12,
                "passes": 7,
                "progressive_passes": 3,
                "completed_progressive_passes": 3,
                "progressive_distance": 45.0,
                "shots": 2,
                "xg": 0.4,
            },
        ]
    )

    aggregate = aggregate_player_metrics(match_rows)

    assert aggregate.loc[0, "matches"] == 2
    assert aggregate.loc[0, "progressive_passes"] == 5
    assert aggregate.loc[0, "xg"] == 0.6
    assert aggregate.loc[0, "progressive_pass_completion_rate"] == 0.8
