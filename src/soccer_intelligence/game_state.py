"""Assign a match score and tactical game state to each event."""

from __future__ import annotations

import pandas as pd


GAME_STATES = ("leading", "drawing", "trailing", "unknown")


def _scoring_team(
    event: pd.Series, home_team_id: int, away_team_id: int
) -> int | None:
    """Return the team awarded a goal, excluding penalty shootouts.

    In the StatsBomb feed, an ``Own Goal Against`` event belongs to the team
    that conceded it, so the opponent—not the event team—receives the goal.
    """
    if event.get("period", 0) == 5:
        return None
    event_team = event.get("team.id")
    if (
        event.get("type.name") == "Shot"
        and event.get("shot.outcome.name") == "Goal"
    ):
        return event_team
    if event.get("type.name") == "Own Goal Against":
        if event_team == home_team_id:
            return away_team_id
        if event_team == away_team_id:
            return home_team_id
    return None


def _state(team_score: int, opponent_score: int) -> str:
    if team_score > opponent_score:
        return "leading"
    if team_score < opponent_score:
        return "trailing"
    return "drawing"


def add_game_state(events: pd.DataFrame, home_team_id: int, away_team_id: int) -> pd.DataFrame:
    """Add score and state *before* each event.

    The event stream is ordered by StatsBomb's event index. Normal goals update
    the score only after their action has been labelled, preventing target
    leakage. The StatsBomb ``Own Goal Against`` event is correctly credited to
    the opponent. Final score validation remains in the pipeline as a guard
    against unexpected source-data changes.
    """
    required = {"index", "team.id", "type.name"}
    missing = required.difference(events.columns)
    if missing:
        raise ValueError(f"events missing required columns: {sorted(missing)}")

    ordered = events.sort_values("index", kind="stable").copy()
    home_score = 0
    away_score = 0
    rows: list[dict[str, object]] = []

    for _, event in ordered.iterrows():
        team_id = event.get("team.id")
        if team_id == home_team_id:
            state = _state(home_score, away_score)
        elif team_id == away_team_id:
            state = _state(away_score, home_score)
        else:
            state = "unknown"

        rows.append(
            {
                "home_score_before": home_score,
                "away_score_before": away_score,
                "game_state": state,
            }
        )

        scoring_team = _scoring_team(event, home_team_id, away_team_id)
        if scoring_team is not None:
            if scoring_team == home_team_id:
                home_score += 1
            elif scoring_team == away_team_id:
                away_score += 1

    labels = pd.DataFrame(rows, index=ordered.index)
    return ordered.join(labels)
