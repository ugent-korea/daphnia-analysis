import streamlit as st
import pandas as pd
import altair as alt
from sqlalchemy import text
from app.core import database


# ===========================================================
# PAGE: Daphnia Records Analysis (Cached + Broods Info)
# ===========================================================
def render():
    st.title("📊 Daphnia Records Analysis")
    st.caption("Automated analysis of Daphnia mortality, environment, and behavior trends")

    # ---- Load cached data (from main app cache) ----
    data = database.get_data()
    by_full = data["by_full"]        # {mother_id: {...}}
    meta = data.get("meta", {})

    # ---- Build broods dataframe from cached meta ----
    broods_df = pd.DataFrame.from_dict(by_full, orient="index")
    if "mother_id" not in broods_df.columns:
        broods_df["mother_id"] = broods_df.index

    broods_df = broods_df[
        [c for c in broods_df.columns if c in ["mother_id", "set_label", "assigned_person"]]
    ].copy()

    # ---- Load records from DB ----
    engine = database.get_engine()
    with engine.connect() as conn:
        records = pd.read_sql(text("SELECT * FROM records"), conn)

    if records.empty:
        st.warning("No records found in the database.")
        st.stop()

    # ---- Normalize and merge ----
    records["mother_id"] = records["mother_id"].astype(str).str.strip().str.upper()
    broods_df["mother_id"] = broods_df["mother_id"].astype(str).str.strip().str.upper()
    broods_df["set_label"] = broods_df["set_label"].astype(str).str.strip().str.upper()
    df = records.merge(broods_df, on="mother_id", how="left")

    # ---- Clean columns ----
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df = df.sort_values("date", ascending=True)  # chronological order

    df["mortality"] = pd.to_numeric(df["mortality"], errors="coerce").fillna(0).astype(int)
    df["life_stage"] = df["life_stage"].fillna("unknown").str.strip().str.lower()
    df["medium_condition"] = df["medium_condition"].fillna("unknown").str.strip().str.lower()
    df["cause_of_death"] = df["cause_of_death"].fillna("unknown").str.strip().str.lower()
    df["egg_development"] = df["egg_development"].fillna("unknown").str.strip().str.lower()
    df["behavior_pre"] = df["behavior_pre"].fillna("unknown").str.strip().str.lower()
    df["behavior_post"] = df["behavior_post"].fillna("unknown").str.strip().str.lower()
    df["set_label"] = df["set_label"].fillna("unknown").str.upper().str.strip()

    # ---- Get all sets from cached broods (even if no records) ----
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
                    broods_df.loc[
                        broods_df["set_label"] == set_name, "assigned_person"
                    ].dropna().unique()
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

    # ===================== KPIs =====================
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Records", f"{total_records:,}")
    col2.metric("Unique Mothers", f"{unique_mothers:,}")
    col3.metric("Total Mortality (n)", f"{total_mortality:,}")
    col4.metric("Avg Life Expectancy (days)", f"{avg_life_expectancy}")

    st.divider()

    # ===========================================================
    # VISUALIZATIONS
    # ===========================================================

    # 1️⃣ Mortality Trends Over Time
    st.subheader("🪦 Mortality Trends Over Time")
    mortality_trend = df.groupby("date", as_index=False)["mortality"].sum()
    chart1 = (
        alt.Chart(mortality_trend)
        .mark_line(point=True)
        .encode(x="date:T", y="mortality:Q", tooltip=["date", "mortality"])
        .properties(height=300)
    )
    st.altair_chart(chart1, use_container_width=True)

    # 2️⃣ Distribution of Causes of Death
    st.subheader("☠️ Distribution of Causes of Death")
    cod = df["cause_of_death"].value_counts().reset_index()
    cod.columns = ["cause", "count"]
    chart2 = (
        alt.Chart(cod)
        .mark_bar()
        .encode(x=alt.X("cause:N", sort="-y"), y="count:Q", color="cause:N", tooltip=["cause", "count"])
        .properties(height=300)
    )
    st.altair_chart(chart2, use_container_width=True)

    # 3️⃣ Life Stage Distribution
    st.subheader("🦠 Life Stage Distribution")
    stage = df["life_stage"].value_counts().reset_index()
    stage.columns = ["life_stage", "count"]
    chart3 = (
        alt.Chart(stage)
        .mark_arc(innerRadius=50)
        .encode(theta="count:Q", color="life_stage:N", tooltip=["life_stage", "count"])
        .properties(height=300)
    )
    st.altair_chart(chart3, use_container_width=True)

    # 4️⃣ Medium Condition Analysis
    st.subheader("🌊 Medium Condition Analysis")
    medium = df["medium_condition"].value_counts().reset_index()
    medium.columns = ["medium_condition", "count"]
    chart4 = (
        alt.Chart(medium)
        .mark_bar()
        .encode(x=alt.X("medium_condition:N", sort="-y"), y="count:Q", color="medium_condition:N", tooltip=["medium_condition", "count"])
        .properties(height=300)
    )
    st.altair_chart(chart4, use_container_width=True)

    # 5️⃣ Egg Development Status
    st.subheader("🥚 Egg Development Status")
    egg = df["egg_development"].value_counts().reset_index()
    egg.columns = ["egg_development", "count"]
    chart5 = (
        alt.Chart(egg)
        .mark_arc(innerRadius=50)
        .encode(theta="count:Q", color="egg_development:N", tooltip=["egg_development", "count"])
        .properties(height=300)
    )
    st.altair_chart(chart5, use_container_width=True)

    # 6️⃣ Behavioral Comparison
    st.subheader("🧠 Behavioral Comparison (Pre vs Post Feeding)")
    behavior_compare = (
        pd.concat(
            [df["behavior_pre"].value_counts().rename("count_pre"),
             df["behavior_post"].value_counts().rename("count_post")],
            axis=1,
        )
        .fillna(0)
        .reset_index()
        .rename(columns={"index": "behavior"})
    )
    behavior_melted = behavior_compare.melt("behavior", var_name="type", value_name="count")
    chart6 = (
        alt.Chart(behavior_melted)
        .mark_bar()
        .encode(x=alt.X("behavior:N", sort="-y"), y="count:Q", color="type:N", tooltip=["behavior", "type", "count"])
        .properties(height=300)
    )
    st.altair_chart(chart6, use_container_width=True)

    # 7️⃣ Mortality by Life Stage
    st.subheader("⚰️ Mortality by Life Stage")
    mort_by_stage = df.groupby("life_stage", as_index=False)["mortality"].mean()
    chart7 = (
        alt.Chart(mort_by_stage)
        .mark_bar()
        .encode(x=alt.X("life_stage:N", sort="-y"), y="mortality:Q", color="life_stage:N", tooltip=["life_stage", "mortality"])
        .properties(height=300)
    )
    st.altair_chart(chart7, use_container_width=True)

    # ===========================================================
    # RAW DATA VIEWER
    # ===========================================================
    st.divider()
    st.subheader("📋 Raw Data Preview")
    st.dataframe(df.sort_values("date", ascending=True).reset_index(drop=True), use_container_width=True, height=400)
