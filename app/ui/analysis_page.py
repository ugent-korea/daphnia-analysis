import streamlit as st
import pandas as pd
import altair as alt
from sqlalchemy import text
import re, unicodedata
from app.core import database


# ===========================================================
# PAGE: Daphnia Records Analysis
# ===========================================================
def render():
    st.title("📊 Daphnia Records Analysis")
    st.caption("Automated analysis of Daphnia mortality, environment, and behavior trends")

    # ---- Load cached broods ----
    data = database.get_data()
    by_full = data["by_full"]
    broods_df = pd.DataFrame.from_dict(by_full, orient="index")
    if "mother_id" not in broods_df.columns:
        broods_df["mother_id"] = broods_df.index
    broods_df = broods_df[
        [c for c in broods_df.columns if c in ["mother_id", "set_label", "assigned_person"]]
    ].copy()

    # ---- Load records ----
    engine = database.get_engine()
    with engine.connect() as conn:
        records = pd.read_sql(text("SELECT * FROM records"), conn)
    if records.empty:
        st.warning("No records found in the database.")
        st.stop()

    # ===========================================================
    # NORMALIZATION + CANONICAL CLEANUP
    # ===========================================================
    def normalize_id(x: str) -> str:
        if not isinstance(x, str):
            return ""
        x = unicodedata.normalize("NFKC", x)
        x = re.sub(r"[\u200B-\u200D\uFEFF]", "", x)
        x = x.replace(" ", "").replace("__", "_").strip()
        return x.upper()

    records["mother_id"] = records["mother_id"].map(normalize_id)
    broods_df["mother_id"] = broods_df["mother_id"].map(normalize_id)
    broods_df["set_label"] = broods_df["set_label"].map(
        lambda s: normalize_id(s) if isinstance(s, str) else s
    )

    def canonical_core(s: str) -> str:
        if not isinstance(s, str):
            return ""
        s = s.strip().split("_")[0]
        s = s.replace(" ", "")
        s = re.sub(r"(\D)(\d)", r"\1.\2", s)
        s = s.replace("..", ".")
        return s.upper()

    records["core_prefix"] = records["mother_id"].map(canonical_core)
    broods_df["core_prefix"] = broods_df["mother_id"].map(canonical_core)

    # ===========================================================
    # CANONICAL MERGE (robust prefix matching)
    # ===========================================================
    records["set_label"] = None
    records["assigned_person"] = None

    for _, row in broods_df.dropna(subset=["core_prefix"]).iterrows():
        prefix = row["core_prefix"]
        mask = records["core_prefix"].fillna("").str.match(rf"^{re.escape(prefix)}(\.|_|$)")
        records.loc[mask, "set_label"] = row.get("set_label")
        records.loc[mask, "assigned_person"] = row.get("assigned_person")

    # ===========================================================
    # CLEAN COLUMNS + SINGLE SAFE EXPLODE
    # ===========================================================
    df = records.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date", ascending=True)

    text_cols = [
        "life_stage", "cause_of_death", "medium_condition",
        "egg_development", "behavior_pre", "behavior_post"
    ]

    # Split text fields into token lists
    for col in text_cols:
        df[col] = (
            df[col]
            .fillna("")
            .astype(str)
            .apply(lambda x: [v.strip().lower() for v in re.split(r"[,/;&]+", x) if v.strip()])
        )

    # Find longest token list length per row
    df["max_len"] = df[text_cols].applymap(len).max(axis=1)

    # Pad shorter lists so lengths match
    for col in text_cols:
        df[col] = df.apply(
            lambda r: r[col] + [r[col][-1]] * (r["max_len"] - len(r[col])) if len(r[col]) < r["max_len"] else r[col],
            axis=1
        )

    # Explode ONCE using the longest-list column (avoids row inflation)
    df = df.explode(text_cols[0], ignore_index=True)
    for col in text_cols[1:]:
        df[col] = df[col].apply(lambda x: x[0] if isinstance(x, list) else x)
    df = df.drop(columns=["max_len"])

    # Remove blanks
    for col in text_cols:
        df = df[df[col].notna()]
        df = df[df[col] != ""]
        df = df[df[col] != "unknown"]

    # ===========================================================
    # TABS
    # ===========================================================
    all_sets = sorted(broods_df["set_label"].dropna().unique().tolist())
    if not all_sets:
        st.warning("⚠️ No sets found in cached broods — check ETL or database sync.")
        st.stop()

    tabs = st.tabs(["🌍 Cumulative"] + [f"Set {s}" for s in all_sets])

    for i, tab in enumerate(tabs):
        with tab:
            if i == 0:
                st.markdown("### 🌍 Cumulative Overview (All Sets Combined)")
                df_sub = df
                assigned_person = "All Researchers"
            else:
                set_name = all_sets[i - 1]
                df_sub = df[df["set_label"] == set_name]
                assigned_person = (
                    broods_df.loc[broods_df["set_label"] == set_name, "assigned_person"]
                    .dropna().unique()
                )
                assigned_person = assigned_person[0] if len(assigned_person) > 0 else "Unassigned"
                st.markdown(f"### 🧬 Set {set_name} Overview")
                st.caption(f"👩 Assigned to: **{assigned_person}**")

            if df_sub.empty:
                st.info("⚠️ No records logged for this set yet.")
            else:
                show_dashboard(df_sub)


# ===========================================================
# DASHBOARD COMPONENT
# ===========================================================
def show_dashboard(df):
    total_records = len(df)
    total_mortality = df["mortality"].sum()
    unique_mothers = df["mother_id"].nunique()

    # Compute average lifespan
    df_life = (
        df.groupby("mother_id")["date"]
        .agg(["min", "max"])
        .dropna()
        .assign(days_alive=lambda x: (x["max"] - x["min"]).dt.days)
    )
    avg_life_expectancy = df_life["days_alive"].mean().round(1) if not df_life.empty else 0

    # KPIs
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Records", f"{total_records:,}")
    col2.metric("Unique Mothers", f"{unique_mothers:,}")
    col3.metric("Total Mortality (n)", f"{total_mortality:,}")
    col4.metric("Avg Life Expectancy (days)", f"{avg_life_expectancy}")

    st.divider()

    # Graphs
    st.subheader("🪦 Mortality Trends Over Time")
    trend = df.groupby("date", as_index=False)["mortality"].sum()
    st.altair_chart(
        alt.Chart(trend)
        .mark_line(point=True)
        .encode(x="date:T", y="mortality:Q", tooltip=["date", "mortality"])
        .properties(height=300),
        use_container_width=True,
    )

    st.subheader("☠️ Distribution of Causes of Death")
    cod = df["cause_of_death"].value_counts().reset_index()
    cod.columns = ["cause", "count"]
    st.altair_chart(
        alt.Chart(cod)
        .mark_bar()
        .encode(x=alt.X("cause:N", sort="-y"), y="count:Q", color="cause:N")
        .properties(height=300),
        use_container_width=True,
    )

    st.subheader("🦠 Life Stage Distribution")
    stage = df["life_stage"].value_counts().reset_index()
    stage.columns = ["life_stage", "count"]
    st.altair_chart(
        alt.Chart(stage)
        .mark_arc(innerRadius=50)
        .encode(theta="count:Q", color="life_stage:N")
        .properties(height=300),
        use_container_width=True,
    )

    st.subheader("🌊 Medium Condition Analysis")
    medium = df["medium_condition"].value_counts().reset_index()
    medium.columns = ["medium_condition", "count"]
    st.altair_chart(
        alt.Chart(medium)
        .mark_bar()
        .encode(x=alt.X("medium_condition:N", sort="-y"), y="count:Q", color="medium_condition:N")
        .properties(height=300),
        use_container_width=True,
    )

    st.subheader("🥚 Egg Development Status")
    egg = df["egg_development"].value_counts().reset_index()
    egg.columns = ["egg_development", "count"]
    st.altair_chart(
        alt.Chart(egg)
        .mark_arc(innerRadius=50)
        .encode(theta="count:Q", color="egg_development:N")
        .properties(height=300),
        use_container_width=True,
    )

    st.subheader("🧠 Behavioral Comparison (Pre vs Post Feeding)")
    behavior = (
        pd.concat(
            [df["behavior_pre"].value_counts().rename("count_pre"),
             df["behavior_post"].value_counts().rename("count_post")],
            axis=1,
        )
        .fillna(0)
        .reset_index()
        .rename(columns={"index": "behavior"})
    )
    melted = behavior.melt("behavior", var_name="type", value_name="count")
    st.altair_chart(
        alt.Chart(melted)
        .mark_bar()
        .encode(x="behavior:N", y="count:Q", color="type:N")
        .properties(height=300),
        use_container_width=True,
    )

    st.subheader("⚰️ Mortality by Life Stage")
    mort_stage = df.groupby("life_stage", as_index=False)["mortality"].mean()
    st.altair_chart(
        alt.Chart(mort_stage)
        .mark_bar()
        .encode(x="life_stage:N", y="mortality:Q", color="life_stage:N")
        .properties(height=300),
        use_container_width=True,
    )

    st.divider()
    st.subheader("📋 Raw Data Preview")
    st.dataframe(df.sort_values("date").reset_index(drop=True), use_container_width=True, height=400)
