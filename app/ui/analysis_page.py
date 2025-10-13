import re
import streamlit as st
import pandas as pd
import altair as alt
from sqlalchemy import text
from app.core import database
from app.core.coder import canonical_core


# ===========================================================
# PAGE: Daphnia Records Analysis
# ===========================================================
def render():
    st.title("📊 Daphnia Records Analysis")
    st.caption("Automated analysis of Daphnia mortality, environment, and behavior trends")

    # ---- Load cached data ----
    data = database.get_data()
    by_full = data["by_full"]
    meta = data.get("meta", {})

    # ---- Convert cached broods to DataFrame ----
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

    # ---- Canonical normalization ----
    def safe_core(x):
        if not x or not isinstance(x, str):
            return None
        s = x.strip().split("_")[0]
        s = re.sub(r"(\D)(\d)", r"\1.\2", s)  # ensure A1→A.1
        s = s.replace("..", ".")
        try:
            return canonical_core(s)
        except Exception:
            return None

    records["canonical_core"] = records["mother_id"].map(safe_core)
    broods_df["canonical_core"] = broods_df["mother_id"].map(safe_core)

    # ---- Fuzzy join by canonical prefix ----
    brood_map = broods_df[["canonical_core", "set_label", "assigned_person"]].dropna()
    records["set_label"] = None
    records["assigned_person"] = None

    for _, row in brood_map.iterrows():
        prefix = row["canonical_core"]
        mask = records["canonical_core"].fillna("").str.startswith(prefix)
        records.loc[mask, "set_label"] = row["set_label"]
        records.loc[mask, "assigned_person"] = row["assigned_person"]

    df = records.copy()

    # ---- Clean columns ----
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df = df.sort_values("date", ascending=True)

    df["mortality"] = pd.to_numeric(df["mortality"], errors="coerce").fillna(0).astype(int)
    text_cols = [
        "life_stage",
        "medium_condition",
        "cause_of_death",
        "egg_development",
        "behavior_pre",
        "behavior_post",
    ]
    for col in text_cols:
        df[col] = df[col].fillna("").str.strip().str.lower()
    df["set_label"] = df["set_label"].fillna("unknown").str.upper().str.strip()

    # ---- Safe split & explode (comma-separated) ----
    split_cols = ["cause_of_death", "medium_condition", "behavior_pre", "behavior_post"]

    for col in split_cols:
        df[col] = (
            df[col]
            .astype(str)
            .apply(
                lambda x: [v.strip().lower() for v in re.split(r"[,/;&]+", x) if v.strip()]
                if x.strip()
                else []
            )
        )

    # Ensure explode-safe structure
    for col in split_cols:
        df[col] = df[col].apply(lambda x: x if isinstance(x, list) else [x])

    # Explode one column at a time (avoids mismatch errors)
    for col in split_cols:
        df = df.explode(col, ignore_index=True)

    # ---- Tabs ----
    all_sets = sorted(broods_df["set_label"].dropna().unique())
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
                    .dropna()
                    .unique()
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

    # Compute average lifespan per mother_id
    df_life = (
        df.groupby("mother_id")["date"]
        .agg(["min", "max"])
        .dropna()
        .assign(days_alive=lambda x: (x["max"] - x["min"]).dt.days)
    )
    avg_life_expectancy = df_life["days_alive"].mean().round(1) if not df_life.empty else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Records", f"{total_records:,}")
    col2.metric("Unique Mothers", f"{unique_mothers:,}")
    col3.metric("Total Mortality (n)", f"{total_mortality:,}")
    col4.metric("Avg Life Expectancy (days)", f"{avg_life_expectancy}")

    st.divider()

    # Helper to skip blanks/unknowns
    def clean_nonempty(series):
        return series.dropna().loc[~series.str.lower().isin(["", "unknown", "nan", "none"])]

    # ===========================================================
    # VISUALIZATIONS
    # ===========================================================
    st.subheader("🪦 Mortality Trends Over Time")
    mortality_trend = df.groupby("date", as_index=False)["mortality"].sum()
    st.altair_chart(
        alt.Chart(mortality_trend)
        .mark_line(point=True)
        .encode(x="date:T", y="mortality:Q", tooltip=["date", "mortality"])
        .properties(height=300),
        use_container_width=True,
    )

    st.subheader("☠️ Distribution of Causes of Death")
    cod = clean_nonempty(df["cause_of_death"]).value_counts().reset_index()
    cod.columns = ["cause", "count"]
    st.altair_chart(
        alt.Chart(cod)
        .mark_bar()
        .encode(x=alt.X("cause:N", sort="-y"), y="count:Q", color="cause:N", tooltip=["cause", "count"])
        .properties(height=300),
        use_container_width=True,
    )

    st.subheader("🦠 Life Stage Distribution")
    stage = clean_nonempty(df["life_stage"]).value_counts().reset_index()
    stage.columns = ["life_stage", "count"]
    st.altair_chart(
        alt.Chart(stage)
        .mark_arc(innerRadius=50)
        .encode(theta="count:Q", color="life_stage:N", tooltip=["life_stage", "count"])
        .properties(height=300),
        use_container_width=True,
    )

    st.subheader("🌊 Medium Condition Analysis")
    medium = clean_nonempty(df["medium_condition"]).value_counts().reset_index()
    medium.columns = ["medium_condition", "count"]
    st.altair_chart(
        alt.Chart(medium)
        .mark_bar()
        .encode(x=alt.X("medium_condition:N", sort="-y"), y="count:Q", color="medium_condition:N", tooltip=["medium_condition", "count"])
        .properties(height=300),
        use_container_width=True,
    )

    st.subheader("🥚 Egg Development Status")
    egg = clean_nonempty(df["egg_development"]).value_counts().reset_index()
    egg.columns = ["egg_development", "count"]
    st.altair_chart(
        alt.Chart(egg)
        .mark_arc(innerRadius=50)
        .encode(theta="count:Q", color="egg_development:N", tooltip=["egg_development", "count"])
        .properties(height=300),
        use_container_width=True,
    )

    st.subheader("🧠 Behavioral Comparison (Pre vs Post Feeding)")
    pre = clean_nonempty(df["behavior_pre"]).value_counts().rename("count_pre")
    post = clean_nonempty(df["behavior_post"]).value_counts().rename("count_post")
    behavior_compare = pd.concat([pre, post], axis=1).fillna(0).reset_index().rename(columns={"index": "behavior"})
    behavior_melted = behavior_compare.melt("behavior", var_name="type", value_name="count")
    st.altair_chart(
        alt.Chart(behavior_melted)
        .mark_bar()
        .encode(x=alt.X("behavior:N", sort="-y"), y="count:Q", color="type:N", tooltip=["behavior", "type", "count"])
        .properties(height=300),
        use_container_width=True,
    )

    st.subheader("⚰️ Mortality by Life Stage")
    clean_stage_df = df[df["life_stage"].isin(clean_nonempty(df["life_stage"]).unique())]
    mort_by_stage = clean_stage_df.groupby("life_stage", as_index=False)["mortality"].mean()
    st.altair_chart(
        alt.Chart(mort_by_stage)
        .mark_bar()
        .encode(x=alt.X("life_stage:N", sort="-y"), y="mortality:Q", color="life_stage:N", tooltip=["life_stage", "mortality"])
        .properties(height=300),
        use_container_width=True,
    )

    st.divider()
    st.subheader("📋 Raw Data Preview")
    st.dataframe(df.sort_values("date", ascending=True).reset_index(drop=True), use_container_width=True, height=400)
