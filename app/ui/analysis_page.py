import re
import unicodedata
import pandas as pd
import altair as alt
import streamlit as st
from sqlalchemy import text
from app.core import database


# ===========================================================
# PAGE: Daphnia Records Analysis (Stable Version)
# ===========================================================
def render():
    st.title("📊 Daphnia Records Analysis")
    st.caption("Automated analysis of Daphnia mortality, environment, and behavior trends")

    # ---- Load cached broods ----
    try:
        data = database.get_data()
        by_full = data.get("by_full", {})
        broods_df = pd.DataFrame.from_dict(by_full, orient="index")
        if "mother_id" not in broods_df.columns:
            broods_df["mother_id"] = broods_df.index
        broods_df = broods_df[
            [c for c in broods_df.columns if c in ["mother_id", "set_label", "assigned_person"]]
        ].copy()
    except Exception as e:
        st.error(f"❌ Failed to load broods cache: {e}")
        return

    # ---- Load records ----
    try:
        engine = database.get_engine()
        with engine.connect() as conn:
            records = pd.read_sql(text("SELECT * FROM records"), conn)
    except Exception as e:
        st.error(f"❌ Failed to load records table: {e}")
        return

    if records.empty:
        st.warning("⚠️ No records found in the database.")
        st.stop()

    # ---- Normalize IDs ----
    def normalize_id(x):
        if not isinstance(x, str):
            return ""
        x = unicodedata.normalize("NFKC", x)
        x = re.sub(r"[\u200B-\u200D\uFEFF]", "", x)
        return x.strip().upper()

    records["mother_id"] = records["mother_id"].map(normalize_id)
    broods_df["mother_id"] = broods_df["mother_id"].map(normalize_id)

    # ---- Merge records ↔ broods (exact like connectivity test) ----
    df = records.merge(broods_df, on="mother_id", how="left")

    # ---- Date + cleaning ----
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date")
    df["mortality"] = pd.to_numeric(df.get("mortality", 0), errors="coerce").fillna(0).astype(int)

    # ---- Text cleaning ----
    text_cols = [
        "life_stage", "cause_of_death", "medium_condition",
        "egg_development", "behavior_pre", "behavior_post"
    ]
    for col in text_cols:
        df[col] = df[col].fillna("").astype(str).str.strip().str.lower()

    # ---- Identify sets ----
    all_sets = sorted(df["set_label"].dropna().unique().tolist())
    if not all_sets:
        st.warning("⚠️ No set_label values found after merge — check broods metadata.")
        st.dataframe(df.head(), use_container_width=True)
        st.stop()

    # ---- Tabs ----
    tabs = st.tabs(["🌍 Cumulative"] + [f"Set {s}" for s in all_sets])

    for i, tab in enumerate(tabs):
        with tab:
            if i == 0:
                df_sub = df
                assigned_person = "All Researchers"
                st.markdown("### 🌍 Cumulative Overview (All Sets Combined)")
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

    df_life = (
        df.groupby("mother_id")["date"]
        .agg(["min", "max"])
        .dropna()
        .assign(days_alive=lambda x: (x["max"] - x["min"]).dt.days)
    )
    avg_life_expectancy = df_life["days_alive"].mean().round(1) if not df_life.empty else 0

    # KPIs
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Records", f"{total_records:,}")
    c2.metric("Unique Mothers", f"{unique_mothers:,}")
    c3.metric("Avg Life Expectancy (days)", f"{avg_life_expectancy}")

    st.divider()

    # ===================== Charts =====================
    def safe_chart(title, df_func):
        try:
            st.subheader(title)
            chart_df = df_func()
            if chart_df.empty:
                st.info("No data available for this chart.")
                return
            st.altair_chart(chart_df, use_container_width=True)
        except Exception as e:
            st.error(f"Chart error ({title}): {e}")

    # Mortality trend
    def trend_chart():
        t = df.groupby("date", as_index=False)["mortality"].sum()
        return (
            alt.Chart(t)
            .mark_line(point=True)
            .encode(x="date:T", y="mortality:Q", tooltip=["date", "mortality"])
            .properties(height=300)
        )

    # Cause of death
    def cod_chart():
        cod = df["cause_of_death"].value_counts().reset_index()
        cod.columns = ["cause", "count"]
        return (
            alt.Chart(cod)
            .mark_bar()
            .encode(x=alt.X("cause:N", sort="-y"), y="count:Q", color="cause:N")
            .properties(height=300)
        )

    # Life stage
    def stage_chart():
        s = df["life_stage"].value_counts().reset_index()
        s.columns = ["life_stage", "count"]
        return (
            alt.Chart(s)
            .mark_arc(innerRadius=50)
            .encode(theta="count:Q", color="life_stage:N", tooltip=["life_stage", "count"])
            .properties(height=300)
        )

    # Medium condition
    def medium_chart():
        m = df["medium_condition"].value_counts().reset_index()
        m.columns = ["medium_condition", "count"]
        return (
            alt.Chart(m)
            .mark_bar()
            .encode(x=alt.X("medium_condition:N", sort="-y"), y="count:Q", color="medium_condition:N")
            .properties(height=300)
        )

    # Egg development
    def egg_chart():
        e = df["egg_development"].value_counts().reset_index()
        e.columns = ["egg_development", "count"]
        return (
            alt.Chart(e)
            .mark_arc(innerRadius=50)
            .encode(theta="count:Q", color="egg_development:N", tooltip=["egg_development", "count"])
            .properties(height=300)
        )

    # Behavior comparison
    def behavior_chart():
        pre = df["behavior_pre"].value_counts()
        post = df["behavior_post"].value_counts()
        b = pd.concat([pre.rename("count_pre"), post.rename("count_post")], axis=1).fillna(0)
        b = b.reset_index().rename(columns={"index": "behavior"})
        b = b.melt("behavior", var_name="type", value_name="count")
        return (
            alt.Chart(b)
            .mark_bar()
            .encode(x=alt.X("behavior:N", sort="-y"), y="count:Q", color="type:N")
            .properties(height=300)
        )

    # Mortality by stage
    def mort_stage_chart():
        m = df.groupby("life_stage", as_index=False)["mortality"].mean()
        return (
            alt.Chart(m)
            .mark_bar()
            .encode(x=alt.X("life_stage:N", sort="-y"), y="mortality:Q", color="life_stage:N")
            .properties(height=300)
        )

    safe_chart("🪦 Mortality Trends Over Time", trend_chart)
    safe_chart("☠️ Distribution of Causes of Death", cod_chart)
    safe_chart("🦠 Life Stage Distribution", stage_chart)
    safe_chart("🌊 Medium Condition Analysis", medium_chart)
    safe_chart("🥚 Egg Development Status", egg_chart)
    safe_chart("🧠 Behavioral Comparison (Pre vs Post Feeding)", behavior_chart)
    safe_chart("⚰️ Mortality by Life Stage", mort_stage_chart)

    st.divider()
    st.subheader("📋 Raw Data Preview")
    st.dataframe(df.sort_values("date").reset_index(drop=True), use_container_width=True, height=400)
