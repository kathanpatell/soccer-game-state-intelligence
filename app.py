"""Interactive view of the derived game-state metrics."""

from pathlib import Path
import json

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent
METRICS_DIR = PROJECT_ROOT / "data" / "processed"


@st.cache_data
def load_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def scope_label(path: Path) -> str:
    return "Match " + path.stem.replace("player_metrics_", "")


def pitch_figure(passes: pd.DataFrame) -> go.Figure:
    """Render a horizontal StatsBomb-sized pitch with progressive pass paths."""
    fig = go.Figure()
    pitch_line = "rgba(248, 250, 252, 0.65)"
    pitch_fill = "rgba(30, 41, 59, 0.35)"
    shapes = [
        dict(type="rect", x0=0, y0=0, x1=120, y1=80, line=dict(color=pitch_line), fillcolor=pitch_fill),
        dict(type="line", x0=60, y0=0, x1=60, y1=80, line=dict(color=pitch_line)),
        dict(type="circle", x0=50, y0=30, x1=70, y1=50, line=dict(color=pitch_line)),
        dict(type="rect", x0=0, y0=18, x1=18, y1=62, line=dict(color=pitch_line)),
        dict(type="rect", x0=102, y0=18, x1=120, y1=62, line=dict(color=pitch_line)),
        dict(type="rect", x0=0, y0=30, x1=6, y1=50, line=dict(color=pitch_line)),
        dict(type="rect", x0=114, y0=30, x1=120, y1=50, line=dict(color=pitch_line)),
    ]
    for row in passes.itertuples(index=False):
        color = "#6ee7b7" if bool(row.is_completed) else "#fca5a5"
        shapes.append(
            dict(
                type="line",
                x0=row.start_x,
                y0=row.start_y,
                x1=row.end_x,
                y1=row.end_y,
                line=dict(color=color, width=2),
                opacity=0.75,
            )
        )

    custom_data = passes[["minute", "game_state", "end_x", "end_y", "is_completed"]]
    fig.add_trace(
        go.Scatter(
            x=passes["start_x"],
            y=passes["start_y"],
            mode="markers",
            marker=dict(color="#f8fafc", size=5),
            customdata=custom_data,
            hovertemplate=(
                "Minute %{customdata[0]}<br>State: %{customdata[1]}<br>"
                "End: (%{customdata[2]:.0f}, %{customdata[3]:.0f})<br>"
                "Completed: %{customdata[4]}<extra></extra>"
            ),
            name="Pass start",
        )
    )
    fig.update_layout(
        shapes=shapes,
        height=520,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        xaxis=dict(range=[-3, 123], visible=False, fixedrange=True),
        yaxis=dict(range=[-3, 83], visible=False, fixedrange=True, scaleanchor="x", scaleratio=1),
    )
    return fig


def cumulative_xg_figure(shots: pd.DataFrame) -> go.Figure:
    """Render cumulative xG for each team, with shot-goal markers."""
    fig = go.Figure()
    for team, team_shots in shots.groupby("team", sort=True):
        ordered = team_shots.sort_values("event_index").copy()
        ordered["cumulative_xg"] = ordered["xg"].cumsum()
        fig.add_trace(
            go.Scatter(
                x=ordered["minute"],
                y=ordered["cumulative_xg"],
                mode="lines+markers",
                line=dict(shape="hv"),
                name=team,
                customdata=ordered[["player", "xg", "outcome"]],
                hovertemplate=(
                    "%{fullData.name}<br>Minute %{x}<br>Cumulative xG %{y:.2f}<br>"
                    "%{customdata[0]} shot: %{customdata[1]:.2f} xG<br>"
                    "Outcome: %{customdata[2]}<extra></extra>"
                ),
            )
        )
        goals = ordered.loc[ordered["outcome"].eq("Goal")]
        if not goals.empty:
            fig.add_trace(
                go.Scatter(
                    x=goals["minute"],
                    y=goals["cumulative_xg"],
                    mode="markers",
                    marker=dict(symbol="star", size=12),
                    name=f"{team} goal",
                    hovertemplate=f"{team} goal at minute %{{x}}<extra></extra>",
                )
            )
    fig.update_layout(
        height=420,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend_title_text="",
        xaxis_title="Match minute",
        yaxis_title="Cumulative xG",
        hovermode="x unified",
    )
    return fig

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
selected_match_id = None
if not selected_scope.startswith("Season overview"):
    selected_match_id = int(scope_options[selected_scope].stem.replace("player_metrics_", ""))

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

visual_events_file = METRICS_DIR / "season_visual_events.csv"
if visual_events_file.is_file():
    visual_events = load_csv(visual_events_file)
    if selected_match_id is not None:
        visual_events = visual_events.loc[visual_events["match_id"].eq(selected_match_id)].copy()

    st.divider()
    st.header("Tactical views")
    pitch_events = visual_events.loc[visual_events["event_type"].eq("Progressive pass")].copy()
    if selected_state != "all":
        pitch_events = pitch_events.loc[pitch_events["game_state"].eq(selected_state)]

    st.subheader("Progressive-pass pitch map")
    if pitch_events.empty:
        st.info("No progressive passes match the selected view and game-state filter.")
    else:
        pitch_player = st.selectbox(
            "Pitch-map player",
            sorted(pitch_events["player"].dropna().unique()),
            key="pitch-map-player",
        )
        selected_passes = pitch_events.loc[pitch_events["player"].eq(pitch_player)]
        st.caption(
            f"{len(selected_passes)} progressive passes · green = completed · red = incomplete"
        )
        st.plotly_chart(pitch_figure(selected_passes), use_container_width=True)

    st.subheader("Cumulative xG timeline")
    shots = visual_events.loc[visual_events["event_type"].eq("Shot")].copy()
    match_options = (
        shots[["match_id", "match_label", "match_date"]]
        .drop_duplicates()
        .sort_values(["match_date", "match_label"])
    )
    if shots.empty:
        st.info("No shot events are available for this view.")
    else:
        labels = {
            int(row.match_id): f"{row.match_label} — {row.match_date}"
            for row in match_options.itertuples(index=False)
        }
        default_index = 0
        if selected_match_id is not None and selected_match_id in labels:
            default_index = list(labels).index(selected_match_id)
        timeline_match = st.selectbox(
            "Match for xG timeline",
            list(labels),
            index=default_index,
            format_func=lambda match_id: labels[match_id],
        )
        timeline_shots = shots.loc[shots["match_id"].eq(timeline_match)]
        st.caption("Stars indicate goals scored from shots; own goals do not have an xG value.")
        st.plotly_chart(cumulative_xg_figure(timeline_shots), use_container_width=True)
else:
    st.info(
        "Run the season pipeline again to generate the compact event data required for pitch maps and xG timelines."
    )
