"""Transparent player and team metrics derived from event data."""

from __future__ import annotations

import math

import pandas as pd


PROGRESSIVE_DISTANCE_THRESHOLD = 10.0


def _x_coordinate(value: object) -> float:
    """Extract an x coordinate from a StatsBomb location, returning NaN if absent."""
    if isinstance(value, (list, tuple)) and value:
        return float(value[0])
    return math.nan


def _y_coordinate(value: object) -> float:
    """Extract a y coordinate from a StatsBomb location, returning NaN if absent."""
    if isinstance(value, (list, tuple)) and len(value) > 1:
        return float(value[1])
    return math.nan


def add_action_features(events: pd.DataFrame) -> pd.DataFrame:
    """Add explicit action features used in the MVP metrics table."""
    data = events.copy()
    data["is_pass"] = data["type.name"].eq("Pass")
    data["is_shot"] = data["type.name"].eq("Shot")
    xg = data.get("shot.statsbomb_xg", pd.Series(index=data.index, dtype=float))
    pass_outcome = data.get("pass.outcome.name", pd.Series(index=data.index, dtype=object))
    data["xg"] = pd.to_numeric(xg, errors="coerce").fillna(0.0)
    data["is_completed_pass"] = data["is_pass"] & pass_outcome.isna()

    start_x = data.get("location", pd.Series(index=data.index, dtype=object)).map(_x_coordinate)
    end_x = data.get("pass.end_location", pd.Series(index=data.index, dtype=object)).map(_x_coordinate)
    data["forward_pass_distance"] = (end_x - start_x).where(data["is_pass"], 0.0).fillna(0.0)
    data["is_progressive_pass"] = (
        data["is_pass"]
        & (data["forward_pass_distance"] >= PROGRESSIVE_DISTANCE_THRESHOLD)
    )
    data["is_completed_progressive_pass"] = (
        data["is_progressive_pass"] & data["is_completed_pass"]
    )
    data["progressive_distance"] = data["forward_pass_distance"].where(
        data["is_progressive_pass"], 0.0
    )
    return data


def player_game_state_metrics(events: pd.DataFrame) -> pd.DataFrame:
    """Aggregate game-state metrics by player; exclude non-player events."""
    features = add_action_features(events)
    group_columns = ["match_id", "team.name", "player.name", "game_state"]
    available = [column for column in group_columns if column in features.columns]
    if len(available) != len(group_columns):
        missing = sorted(set(group_columns).difference(available))
        raise ValueError(f"events missing metric grouping columns: {missing}")

    player_events = features.dropna(subset=["player.name"]).copy()
    metrics = (
        player_events.groupby(group_columns, dropna=False)
        .agg(
            events=("index", "size"),
            passes=("is_pass", "sum"),
            progressive_passes=("is_progressive_pass", "sum"),
            completed_progressive_passes=("is_completed_progressive_pass", "sum"),
            progressive_distance=("progressive_distance", "sum"),
            shots=("is_shot", "sum"),
            xg=("xg", "sum"),
        )
        .reset_index()
    )
    metrics["progressive_pass_completion_rate"] = (
        metrics["completed_progressive_passes"]
        .div(metrics["progressive_passes"].where(metrics["progressive_passes"] > 0))
        .round(3)
    )
    metrics["xg_per_shot"] = metrics["xg"].div(metrics["shots"].where(metrics["shots"] > 0)).round(3)
    return metrics


def aggregate_player_metrics(match_metrics: pd.DataFrame) -> pd.DataFrame:
    """Combine match rows into a player-by-state season view.

    The aggregate retains the number of matches a player appeared in, so a
    dashboard user can distinguish a strong total across many matches from a
    one-match outlier.
    """
    group_columns = ["team.name", "player.name", "game_state"]
    sum_columns = [
        "events",
        "passes",
        "progressive_passes",
        "completed_progressive_passes",
        "progressive_distance",
        "shots",
        "xg",
    ]
    required = set(group_columns + sum_columns + ["match_id"])
    missing = sorted(required.difference(match_metrics.columns))
    if missing:
        raise ValueError(f"match metrics missing aggregation columns: {missing}")

    aggregate = (
        match_metrics.groupby(group_columns, dropna=False)
        .agg(
            matches=("match_id", "nunique"),
            **{column: (column, "sum") for column in sum_columns},
        )
        .reset_index()
    )
    aggregate["xg"] = aggregate["xg"].round(6)
    aggregate["progressive_distance"] = aggregate["progressive_distance"].round(2)
    aggregate["progressive_pass_completion_rate"] = (
        aggregate["completed_progressive_passes"]
        .div(aggregate["progressive_passes"].where(aggregate["progressive_passes"] > 0))
        .round(3)
    )
    aggregate["xg_per_shot"] = (
        aggregate["xg"].div(aggregate["shots"].where(aggregate["shots"] > 0)).round(3)
    )
    return aggregate


def visual_event_rows(events: pd.DataFrame, match_metadata: dict) -> pd.DataFrame:
    """Return the compact event subset required for the interactive visuals.

    Only progressive passes and shots are retained. This keeps the deployable
    CSV small while preserving every coordinate needed for a pitch map and the
    full shot sequence needed for a cumulative xG timeline.
    """
    event_columns = ["match_id", "index", "minute", "period", "team.name", "player.name", "game_state"]
    missing = sorted(set(event_columns).difference(events.columns))
    if missing:
        raise ValueError(f"events missing visualisation columns: {missing}")

    event_location = events.get("location", pd.Series(index=events.index, dtype=object))
    end_location = events.get("pass.end_location", pd.Series(index=events.index, dtype=object))
    shot_outcome = events.get("shot.outcome.name", pd.Series(index=events.index, dtype=object))
    base = pd.DataFrame(
        {
            "match_id": events["match_id"],
            "event_index": events["index"],
            "minute": events["minute"],
            "period": events["period"],
            "team": events["team.name"],
            "player": events["player.name"],
            "game_state": events["game_state"],
            "start_x": event_location.map(_x_coordinate),
            "start_y": event_location.map(_y_coordinate),
            "end_x": end_location.map(_x_coordinate),
            "end_y": end_location.map(_y_coordinate),
            "xg": events["xg"],
            "outcome": shot_outcome,
        },
        index=events.index,
    )
    home = match_metadata["home_team"]["home_team_name"]
    away = match_metadata["away_team"]["away_team_name"]
    base["match_label"] = f"{home} vs {away}"
    base["match_date"] = match_metadata["match_date"]

    progressive = base.loc[events["is_progressive_pass"]].copy()
    progressive["event_type"] = "Progressive pass"
    progressive["is_completed"] = events.loc[progressive.index, "is_completed_pass"].astype(bool)

    shots = base.loc[events["is_shot"]].copy()
    shots["event_type"] = "Shot"
    shots["is_completed"] = pd.NA

    output_columns = [
        "match_id",
        "match_label",
        "match_date",
        "event_index",
        "minute",
        "period",
        "team",
        "player",
        "game_state",
        "event_type",
        "start_x",
        "start_y",
        "end_x",
        "end_y",
        "xg",
        "outcome",
        "is_completed",
    ]
    return pd.concat([progressive, shots], ignore_index=True).loc[:, output_columns]
