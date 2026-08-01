# Game-State Tactical Intelligence

An open, reproducible soccer analytics project that asks a specific scouting
question: **which players improve territory and chance creation when their team
is behind?**

## Live demo

[Open the interactive dashboard](https://soccer-game-state-intelligence.streamlit.app/)

Rather than ranking players by aggregate totals, the project assigns every
event a game state (leading, drawing, or trailing) based on the score *before*
the event. It then reports passing progression and expected-goal creation by
player, team, and game state.

## What is included

- A downloader for [StatsBomb Open Data](https://github.com/statsbomb/open-data)
- Leakage-safe, event-level game-state labels
- Player metrics for shots, xG, progressive passes, progressive distance, and
  completed progressive passes
- A Streamlit dashboard for comparing players and inspecting individual matches
- Tests covering the scoreline and game-state logic

## Important analytical choices

- **Game state is measured immediately before an action.** A goal is not
  incorrectly attributed to the scorer while their team is already leading.
- **Shootouts are excluded.** They do not describe normal match state.
- **Progression is transparent, not proprietary.** A progressive pass advances
  the ball at least 10 StatsBomb pitch units toward the opponent's goal. This is
  a simple MVP definition, deliberately stated in the app and code.
- The first version reports totals. Do not use these as talent rankings until
  minutes played, opponent strength, and role/position are added.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .

# Inspect available public competitions and seasons
python -m soccer_intelligence.download --list-competitions

# Replace these IDs with a competition/season shown by the prior command
python -m soccer_intelligence.download --competition 43 --season 106

# Create a compact, deployable all-matches dataset.
python -m soccer_intelligence.pipeline --season-dir data/raw/competition_43_season_106
streamlit run app.py
```

The pipeline writes fetched source data to `data/raw/` and derived analysis
files to `data/processed/`; neither is committed. The Streamlit app displays
clear setup instructions until processed data exists.

## Suggested first analysis

Start with one complete competition, then use the dashboard to identify:

1. Players whose progressive passing rises when trailing.
2. Whether that increased volume also increases xG created.
3. Match-level examples that make the finding believable to a non-technical
   reader.

Turn the best finding into a short write-up: question, data scope, method,
result, one visual, and limitations. That is much more compelling than a large
dashboard with no conclusion.

## Roadmap

1. Add minutes played and per-90 rates.
2. Separate open-play and set-piece actions.
3. Adjust comparisons for opponent, match minute, and position.
4. Add possession-value / sequence features, then validate that they improve
   usefulness over the transparent baseline.

## Data and attribution

This project uses StatsBomb Open Data. Review and follow its repository licence
and attribution requirements before publishing or redistributing data. The
code does not claim coverage of every league or season.

## Publish it on GitHub and Streamlit Community Cloud

The season pipeline creates two small derived files that are intentionally
allowed through `.gitignore`: `season_player_metrics.csv` and
`season_metadata.json`. They give a visitor a working all-matches dashboard
without committing raw event files. Keep the StatsBomb attribution in this
README.

1. Create an empty GitHub repository named `soccer-game-state-intelligence`.
2. From this folder, commit and push the project:

   ```bash
   git init
   git add .
   git commit -m "Publish game-state tactical intelligence dashboard"
   git branch -M main
   git remote add origin https://github.com/YOUR-USERNAME/soccer-game-state-intelligence.git
   git push -u origin main
   ```

3. In [Streamlit Community Cloud](https://share.streamlit.io/), create an app
   from that GitHub repository with `main` as the branch and `app.py` as the
   entry point. Its requirements are defined in `pyproject.toml`.
4. Add the live URL and repository URL to your personal portfolio with the
   one-sentence description below.

> An interactive soccer analytics dashboard that measures player progression
> and chance creation by leading, drawing, and trailing game states, built with
> StatsBomb Open Data.
