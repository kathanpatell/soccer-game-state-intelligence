"""Interactive view of the derived game-state metrics."""

from pathlib import Path
import json

import pandas as pd
import plotly.express as px
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent
METRICS_DIR = PROJECT_ROOT / "data" / "processed"


@st.cache_data
def load_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def scope_label(path: Path) -> str:
    return "Match " + path.stem.replace("player_metrics_", "")

st.set_page_config(page_title="Game-State Tactical Intelligence", layout="wide")
st.title("Game-State Tactical Intelligence")
st.caption("Which players improve progression and chance creation when their team is behind?")

match_metric_files = sorted(METRICS_DIR.glob("player_metrics_*.csv"))
season_metric_file = METRICS_DIR / "season_player_metrics.csv"
if not match_metric_files and not season_metric_file.is_file():
    st.info(
        "No processed matches yet. Follow the README: download a StatsBomb Open Data season, "
        "then run `python -m soccer_intelligence.pipeline --match-id ...`."
    )
    st.stop()

scope_options: dict[str, Path] = {scope_label(path): path for path in match_metric_files}
if season_metric_file.is_file():
    scope_options = {"Season overview (all processed matches)": season_metric_file, **scope_options}
selected_scope = st.sidebar.selectbox("View", list(scope_options), index=0)
metrics = load_csv(scope_options[selected_scope])

season_metadata_file = METRICS_DIR / "season_metadata.json"
if selected_scope.startswith("Season overview") and season_metadata_file.is_file():
    metadata = json.loads(season_metadata_file.read_text(encoding="utf-8"))
    st.caption(f"{metadata['season_label']} · {metadata['matches_processed']} matches · StatsBomb Open Data")
state_options = ["all", *sorted(metrics["game_state"].dropna().unique())]
selected_state = st.sidebar.selectbox("Game state", state_options, index=0)
view = metrics if selected_state == "all" else metrics.query("game_state == @selected_state")

st.caption(
    "A progressive pass advances the ball at least 10 StatsBomb pitch units toward goal. "
    "States and scores are measured before the event. Totals are not per-90 rates."
)

top = view.sort_values(["progressive_passes", "xg"], ascending=False).head(12)
left, right = st.columns(2)
left.subheader("Top progression totals")
table_columns = ["player.name", "team.name", "game_state"]
if "matches" in top.columns:
    table_columns.append("matches")
table_columns += ["progressive_passes", "completed_progressive_passes", "progressive_distance"]
left.dataframe(
    top[table_columns],
    use_container_width=True,
    hide_index=True,
)
right.subheader("Chance creation and progression")
chart = px.scatter(
    view,
    x="progressive_passes",
    y="xg",
    size="events",
    color="team.name",
    hover_name="player.name",
    hover_data=["game_state", "shots", "completed_progressive_passes"],
    labels={"xg": "Expected goals from shots", "progressive_passes": "Progressive passes"},
)
right.plotly_chart(chart, use_container_width=True)

st.subheader("Player-by-state profile")
player = st.selectbox("Player", sorted(metrics["player.name"].dropna().unique()))
profile = metrics.loc[metrics["player.name"] == player].copy()
profile_chart = px.bar(
    profile,
    x="game_state",
    y="progressive_passes",
    color="team.name",
    barmode="group",
    labels={"progressive_passes": "Progressive passes"},
)
st.plotly_chart(profile_chart, use_container_width=True)
