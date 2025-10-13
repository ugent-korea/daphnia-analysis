import streamlit as st
import pandas as pd
import altair as alt
from sqlalchemy import text
import re, unicodedata
from app.core import database


# ===========================================================
# PAGE: Daphnia Records Analysis (Cached + Broods Info)
# ===========================================================
def render():
    st.title("📊 Daphnia Records Analysis")
    st.caption("Automated analysis of Daphnia mortality, environment, and behavior trends")

    # ---- Load cached broods meta ----
    data = database.get_data()
    by_full = data["by_full"]        # {mother_id: {...}}
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
    # CANONICAL MERGE (handles invisible / split / prefix issues)
    # ===========================================================
    records["set_label"] = None
    records["assigned_person"] = None

    for _, row in broods_df.dropna(subset=["core_prefix"]).iterrows():
        prefix = row["core_prefix"]
        mask = records["core_prefix"].fillna("").str.startswith(prefix)
        records.loc[mask, "set_label"] = row.get("set_label")
        records.loc[mask, "assigned_person"] = row.get("assigned_person")

    # Debug unmatched
    unmatched = records.loc[records["set_label"].isna(), "mother_id"].unique()
    if len(unmatched) > 0:
        st.caption(f"⚠️ {len(unmatched)} records not matched to broods (showing first 5):")
        st.code(unmatched[:5])

    # ===========================================================
    # CLEAN COLUMNS + EXPLODE MULTI-ENTRIES
    # ===========================================================
    df = records.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date", ascending=True)

    text_cols = [
        "life_stage", "cause_of_death", "medium_condition",
        "egg_development", "behavior_pre", "behavior_post"
    ]
    for col in text_cols:
        df[col] = (
            df[col]
            .fillna("")
            .astype(str)
            .str.strip()
            .apply(lambda x: [v.strip().lower() for v in re.split(r"[,/;&]+", x) if v.strip()])
        )

    # Normalize list lengths by padding shorter ones with a single element
    max_len = max(df[text_cols].applymap(len).max(axis=1))
    for col in text_cols:
        df[col] = df[col].apply(lambda lst: lst if isinstance(lst, list) else [lst])
        df[col] = df[col].apply(lambda lst: lst + [lst[-1]] * (max_len - len(lst)))

    # Now explode column-by-column safely
    for col in text_cols:
        df = df.explode(col, ignore_index=True)

    # ===========================================================
    # TAB NAVIGATION BY SET
    # ===========================================================
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
    st.subheader("🪦 Mortality Trends Over Time")
    mortality_trend = df.groupby("date", as_index=False)["mortality"].sum()
    st.altair_chart(
        alt.Chart(mortality_trend)
        .mark_line(point=True)
        .encode(x="date:T", y="mortality:Q", tooltip=["date", "mortality"])
        .properties(height=300, width="container"),
        use_container_width=True,
    )

    st.subheader("☠️ Distribution of Causes of Death")
    cod = df["cause_of_death"].value_counts().reset_index()
    cod.columns = ["cause", "count"]
    st.altair_chart(
        alt.Chart(cod)
        .mark_bar()
        .encode(x=alt.X("cause:N", sort="-y"), y="count:Q", color="cause:N", tooltip=["cause", "count"])
        .properties(height=300, width="container"),
        use_container_width=True,
    )

    st.subheader("🦠 Life Stage Distribution")
    stage = df["life_stage"].value_counts().reset_index()
    stage.columns = ["life_stage", "count"]
    st.altair_chart(
        alt.Chart(stage)
        .mark_arc(innerRadius=50)
        .encode(theta="count:Q", color="life_stage:N", tooltip=["life_stage", "count"])
        .properties(height=300, width="container"),
        use_container_width=True,
    )

    st.subheader("🌊 Medium Condition Analysis")
    medium = df["medium_condition"].value_counts().reset_index()
    medium.columns = ["medium_condition", "count"]
    st.altair_chart(
        alt.Chart(medium)
        .mark_bar()
        .encode(x=alt.X("medium_condition:N", sort="-y"), y="count:Q", color="medium_condition:N", tooltip=["medium_condition", "count"])
        .properties(height=300, width="container"),
        use_container_width=True,
    )

    st.subheader("🥚 Egg Development Status")
    egg = df["egg_development"].value_counts().reset_index()
    egg.columns = ["egg_development", "count"]
    st.altair_chart(
        alt.Chart(egg)
        .mark_arc(innerRadius=50)
        .encode(theta="count:Q", color="egg_development:N", tooltip=["egg_development", "count"])
        .properties(height=300, width="container"),
        use_container_width=True,
    )

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
    st.altair_chart(
        alt.Chart(behavior_melted)
        .mark_bar()
        .encode(x=alt.X("behavior:N", sort="-y"), y="count:Q", color="type:N", tooltip=["behavior", "type", "count"])
        .properties(height=300, width="container"),
        use_container_width=True,
    )

    st.subheader("⚰️ Mortality by Life Stage")
    mort_by_stage = df.groupby("life_stage", as_index=False)["mortality"].mean()
    st.altair_chart(
        alt.Chart(mort_by_stage)
        .mark_bar()
        .encode(x=alt.X("life_stage:N", sort="-y"), y="mortality:Q", color="life_stage:N", tooltip=["life_stage", "mortality"])
        .properties(height=300, width="container"),
        use_container_width=True,
    )

    # ===========================================================
    # RAW DATA VIEWER
    # ===========================================================
    st.divider()
    st.subheader("📋 Raw Data Preview")
    st.dataframe(
        df.sort_values("date", ascending=True).reset_index(drop=True),
        use_container_width=True,
        height=400,
    )
