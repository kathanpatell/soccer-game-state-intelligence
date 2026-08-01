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
