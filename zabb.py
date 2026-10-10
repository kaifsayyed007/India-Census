import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="India District Explorer", layout="wide")

ID_COLS = ["State", "District", "Latitude", "Longitude", "District code", "State name"]
RAW_ONLY = ["Population", "Households", "Literacy_rate", "Sex_ratio", "Total_Power_Parity"]


@st.cache_data
def load_data():
    df = pd.read_csv("india.csv")
    return df.dropna(subset=["Latitude", "Longitude"])


def metric_options(df):
    return sorted(c for c in df.select_dtypes("number").columns if c not in ID_COLS)


def pretty(col):
    return col.replace("_", " ")


def get_values(df, col, normalise):
    """Raw counts are mostly just 'big districts are big'. Convert to % share."""
    if not normalise or col in RAW_ONLY:
        return df[col].astype(float), pretty(col)
    if "Household" in col or "household" in col:
        return df[col] / df["Households"] * 100, f"{pretty(col)} (% of households)"
    return df[col] / df["Population"] * 100, f"{pretty(col)} (% of population)"


df = load_data()
metrics = metric_options(df)

# ---------------- Sidebar ----------------
st.sidebar.title("India Data Visualisation")
states = ["Overall India"] + sorted(df["State"].unique())
selected_state = st.sidebar.selectbox("State", states)
primary = st.sidebar.selectbox(
    "Primary parameter (bubble size)", metrics, index=metrics.index("Population") if "Population" in metrics else 0,
    format_func=pretty,
)
secondary = st.sidebar.selectbox(
    "Secondary parameter (colour)", metrics, index=metrics.index("Literacy_rate") if "Literacy_rate" in metrics else 0,
    format_func=pretty,
)
normalise = st.sidebar.toggle("Show as % share (fairer across districts)", value=True)
palette = st.sidebar.selectbox("Colour scale", ["Viridis", "Blues", "Plasma", "RdYlGn", "Turbo"])
basemap = st.sidebar.selectbox("Map style", ["carto-positron", "open-street-map", "carto-darkmatter"])

# ---------------- Data prep ----------------
view = df if selected_state == "Overall India" else df[df["State"] == selected_state]
view = view.copy()
view["_p"], p_label = get_values(view, primary, normalise)
view["_s"], s_label = get_values(view, secondary, normalise)
view = view.replace([np.inf, -np.inf], np.nan)
view["_size"] = view["_p"].fillna(0).clip(lower=0)

if selected_state == "Overall India":
    center, zoom = {"lat": 22.5, "lon": 79.0}, 3.6
else:
    span = max(np.ptp(view["Latitude"]), np.ptp(view["Longitude"]), 1)
    center = {"lat": view["Latitude"].mean(), "lon": view["Longitude"].mean()}
    zoom = float(np.clip(7 - np.log2(span), 3.5, 8))

# ---------------- Header + KPIs ----------------
st.title(f"{selected_state}: {p_label} vs {s_label}")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Districts", f"{len(view):,}")
c2.metric(f"Average {pretty(primary)}", f"{view['_p'].mean():,.2f}")
top = view.loc[view["_p"].idxmax()]
c3.metric("Highest district", top["District"], f"{top['_p']:,.2f}", delta_color="off")
corr = view["_p"].corr(view["_s"]) if primary != secondary else 1.0
c4.metric("Correlation (primary vs secondary)", f"{corr:.2f}" if pd.notna(corr) else "n/a")

tab_map, tab_rank, tab_rel, tab_data = st.tabs(["Map", "Rankings", "Relationship", "Data"])

hover = {"State": True, "_p": ":,.2f", "_s": ":,.2f", "_size": False, "Latitude": False, "Longitude": False}
labels = {"_p": p_label, "_s": s_label}

with tab_map:
    fig = px.scatter_map(
        view, lat="Latitude", lon="Longitude", size="_size", color="_s",
        hover_name="District", hover_data=hover, labels=labels,
        color_continuous_scale=palette, size_max=26 if selected_state != "Overall India" else 18,
        opacity=0.75, center=center, zoom=zoom, map_style=basemap, height=700,
    )
    fig.update_layout(margin={"r": 0, "t": 10, "l": 0, "b": 0}, coloraxis_colorbar={"title": s_label})
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Bubble size = primary parameter, colour = secondary parameter.")

with tab_rank:
    n = st.slider("How many districts?", 5, 25, 10)
    left, right = st.columns(2)
    valid = view.dropna(subset=["_p"])
    for col, data, title in [
        (left, valid.nlargest(n, "_p"), f"Top {n}"),
        (right, valid.nsmallest(n, "_p"), f"Bottom {n}"),
    ]:
        bar = px.bar(
            data.sort_values("_p"), x="_p", y="District", orientation="h",
            hover_data={"State": True}, labels={"_p": p_label}, title=f"{title}: {p_label}",
        )
        bar.update_layout(height=450, margin={"t": 40})
        col.plotly_chart(bar, use_container_width=True)

with tab_rel:
    sc = px.scatter(
        view, x="_p", y="_s", color="State" if selected_state == "Overall India" else None,
        hover_name="District", labels=labels, height=600,
    )
    st.plotly_chart(sc, use_container_width=True)

with tab_data:
    table = view[["State", "District", "_p", "_s"]].rename(columns=labels).sort_values(p_label, ascending=False)
    st.dataframe(table, use_container_width=True, hide_index=True)
    st.download_button("Download CSV", table.to_csv(index=False), "india_view.csv", "text/csv")
