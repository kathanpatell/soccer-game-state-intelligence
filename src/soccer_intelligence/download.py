"""Download a selected StatsBomb Open Data competition and season.

The downloader deliberately takes explicit IDs: data coverage changes, and a
project should record exactly which competition and season it analyzed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from soccer_intelligence.paths import RAW_DATA_DIR, ensure_data_directories


BASE_URL = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
REQUEST_TIMEOUT_SECONDS = 30


def fetch_json(url: str) -> Any:
    """Fetch JSON with a visible error if the remote data source changes."""
    response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def competitions() -> list[dict[str, Any]]:
    return fetch_json(f"{BASE_URL}/competitions.json")


def matches(competition_id: int, season_id: int) -> list[dict[str, Any]]:
    return fetch_json(f"{BASE_URL}/matches/{competition_id}/{season_id}.json")


def save_json(payload: Any, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def download_season(competition_id: int, season_id: int) -> list[int]:
    """Download a match list and every event file for one selected season."""
    ensure_data_directories()
    season_dir = RAW_DATA_DIR / f"competition_{competition_id}_season_{season_id}"
    season_matches = matches(competition_id, season_id)
    save_json(season_matches, season_dir / "matches.json")

    downloaded_ids: list[int] = []
    for match in season_matches:
        match_id = int(match["match_id"])
        events = fetch_json(f"{BASE_URL}/events/{match_id}.json")
        save_json(events, season_dir / "events" / f"{match_id}.json")
        downloaded_ids.append(match_id)
        print(f"Downloaded match {match_id} ({len(events):,} events)")
    return downloaded_ids


def display_competitions() -> None:
    """Print the currently available source coverage in an easy-to-copy form."""
    records = competitions()
    table = pd.DataFrame(records)
    desired_columns = [
        "competition_id",
        "competition_name",
        "country_name",
        "season_id",
        "season_name",
        "match_available",
    ]
    print(table.loc[:, [c for c in desired_columns if c in table.columns]].to_string(index=False))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list-competitions", action="store_true")
    parser.add_argument("--competition", type=int, help="StatsBomb competition ID")
    parser.add_argument("--season", type=int, help="StatsBomb season ID")
    args = parser.parse_args()

    if args.list_competitions:
        display_competitions()
        return
    if args.competition is None or args.season is None:
        parser.error("pass --list-competitions or both --competition and --season")
    downloaded_ids = download_season(args.competition, args.season)
    print(f"Finished: {len(downloaded_ids)} matches saved in {RAW_DATA_DIR}")


if __name__ == "__main__":
    main()
