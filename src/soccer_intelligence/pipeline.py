"""Turn downloaded StatsBomb events into dashboard-ready analysis data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from soccer_intelligence.game_state import add_game_state
from soccer_intelligence.metrics import (
    add_action_features,
    aggregate_player_metrics,
    player_game_state_metrics,
)
from soccer_intelligence.paths import PROCESSED_DATA_DIR, RAW_DATA_DIR, ensure_data_directories


def _find_match_file(match_id: int) -> Path:
    candidates = list(RAW_DATA_DIR.glob(f"competition_*_season_*/events/{match_id}.json"))
    if not candidates:
        raise FileNotFoundError(
            f"No event file found for match {match_id}. Run the downloader first."
        )
    if len(candidates) > 1:
        raise ValueError(f"Match {match_id} exists in more than one local season directory.")
    return candidates[0]


def _match_metadata(event_path: Path, match_id: int) -> dict:
    match_file = event_path.parent.parent / "matches.json"
    matches = json.loads(match_file.read_text(encoding="utf-8"))
    try:
        return next(item for item in matches if int(item["match_id"]) == match_id)
    except StopIteration as error:
        raise ValueError(f"Match {match_id} absent from {match_file}") from error


def _process_match(event_path: Path, metadata: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Process a downloaded match file and write portable CSV outputs."""
    match_id = int(metadata["match_id"])
    raw_events = json.loads(event_path.read_text(encoding="utf-8"))
    events = pd.json_normalize(raw_events)
    events["match_id"] = match_id

    home_team_id = int(metadata["home_team"]["home_team_id"])
    away_team_id = int(metadata["away_team"]["away_team_id"])
    labeled_events = add_game_state(events, home_team_id, away_team_id)
    featured_events = add_action_features(labeled_events)
    metrics = player_game_state_metrics(labeled_events)

    featured_events.to_csv(PROCESSED_DATA_DIR / f"events_{match_id}.csv", index=False)
    metrics.to_csv(PROCESSED_DATA_DIR / f"player_metrics_{match_id}.csv", index=False)

    expected_home = metadata.get("home_score")
    expected_away = metadata.get("away_score")
    goal_outcome = labeled_events.get(
        "shot.outcome.name", pd.Series(index=labeled_events.index, dtype=object)
    )
    normal_goal = (
        labeled_events["type.name"].eq("Shot")
        & goal_outcome.eq("Goal")
        & labeled_events["period"].ne(5)
    )
    own_goal = labeled_events["type.name"].eq("Own Goal Against") & labeled_events["period"].ne(5)
    observed_home = int(
        (normal_goal & labeled_events["team.id"].eq(home_team_id)).sum()
        + (own_goal & labeled_events["team.id"].eq(away_team_id)).sum()
    )
    observed_away = int(
        (normal_goal & labeled_events["team.id"].eq(away_team_id)).sum()
        + (own_goal & labeled_events["team.id"].eq(home_team_id)).sum()
    )
    if (expected_home, expected_away) != (observed_home, observed_away):
        print(
            "WARNING: event-derived score does not match match metadata "
            f"({observed_home}-{observed_away} vs {expected_home}-{expected_away}). "
            "Inspect for own goals before interpreting game state."
        )
    return featured_events, metrics


def process_match(match_id: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Process one downloaded match selected by ID."""
    ensure_data_directories()
    event_path = _find_match_file(match_id)
    metadata = _match_metadata(event_path, match_id)
    return _process_match(event_path, metadata)


def process_season(season_directory: Path) -> pd.DataFrame:
    """Process every downloaded match in a season and write a compact summary."""
    ensure_data_directories()
    match_file = season_directory / "matches.json"
    if not match_file.is_file():
        raise FileNotFoundError(f"Missing {match_file}; choose a downloaded season directory.")
    match_records = json.loads(match_file.read_text(encoding="utf-8"))
    all_metrics: list[pd.DataFrame] = []
    skipped: list[int] = []
    for metadata in match_records:
        match_id = int(metadata["match_id"])
        event_path = season_directory / "events" / f"{match_id}.json"
        if not event_path.is_file():
            skipped.append(match_id)
            continue
        _, metrics = _process_match(event_path, metadata)
        all_metrics.append(metrics)
        print(f"Processed match {match_id}")

    if not all_metrics:
        raise ValueError(f"No event files found under {season_directory / 'events'}")
    combined = pd.concat(all_metrics, ignore_index=True)
    summary = aggregate_player_metrics(combined)
    summary.to_csv(PROCESSED_DATA_DIR / "season_player_metrics.csv", index=False)
    season_label = season_directory.name.replace("competition_", "Competition ").replace("_season_", ", season ")
    metadata = {
        "season_label": season_label,
        "matches_processed": len(all_metrics),
        "matches_skipped": skipped,
        "source": "StatsBomb Open Data",
    }
    (PROCESSED_DATA_DIR / "season_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    print(f"Wrote {len(summary):,} player-state rows for {len(all_metrics)} matches.")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--match-id", type=int)
    group.add_argument(
        "--season-dir",
        type=Path,
        help="Downloaded season directory, e.g. data/raw/competition_43_season_106",
    )
    args = parser.parse_args()
    if args.match_id is not None:
        events, metrics = process_match(args.match_id)
        print(f"Processed {len(events):,} events into {len(metrics):,} player-state rows.")
    else:
        process_season(args.season_dir)


if __name__ == "__main__":
    main()
