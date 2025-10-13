import re
import unicodedata
import pandas as pd
import altair as alt
import streamlit as st
from sqlalchemy import text
from app.core import database


# ===========================================================
# PAGE: Daphnia Records Analysis (Safe & Stable)
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
        st.error(f"❌ Failed to load cached broods: {e}")
        return

    # ---- Load records ----
    try:
        engine = database.get_engine()
        with engine.connect() as conn:
            records = pd.read_sql(text("SELECT * FROM records"), conn)
    except Exception as e:
        st.error(f"❌ Failed to load records from Neon DB: {e}")
        return

    if records.empty:
        st.warning("⚠️ No records found in the database.")
        st.stop()

    # ===========================================================
    # NORMALIZATION
    # ===========================================================
    def normalize_id(x: str) -> str:
        if not isinstance(x, str):
            return ""
        x = unicodedata.normalize("NFKC", x)
        x = re.sub(r"[\u200B-\u200D\uFEFF]", "", x)  # remove zero-width chars
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
        s = re.sub(r"(\D)(\d)", r"\1.\2", s)
        s = s.replace("..", ".")
        return s.upper()

    records["core_prefix"] = records["mother_id"].map(canonical_core)
    broods_df["core_prefix"] = broods_df["mother_id"].map(canonical_core)

    # ===========================================================
    # CANONICAL MERGE (HYBRID SAFE)
    # ===========================================================
    records["set_label"] = None
    records["assigned_person"] = None

    # Fuzzy matching by canonical prefix
    for _, row in broods_df.dropna(subset=["core_prefix"]).iterrows():
        prefix = row["core_prefix"]
        mask = records["core_prefix"].fillna("").str.match(rf"^{re.escape(prefix)}(\.|_|$)")
        records.loc[mask, "set_label"] = row.get("set_label")
        records.loc[mask, "assigned_person"] = row.get("assigned_person")

    # Fallback direct merge for unmatched records
    unmatched = records[records["set_label"].isna()]
    if not unmatched.empty:
        fallback = unmatched.merge(
            broods_df, on="mother_id", how="left", suffixes=("", "_fb")
        )
        for col in ["set_label", "assigned_person"]:
            records.loc[records["set_label"].isna(), col] = fallback[f"{col}_fb"].values

    # ===========================================================
    # CLEAN + SAFE EXPLODE
    # ===========================================================
    df = records.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date", ascending=True)

    text_cols = [
        "life_stage", "cause_of_death", "medium_condition",
        "egg_development", "behavior_pre", "behavior_post"
    ]

    # Safely normalize text columns
    for col in text_cols:
        df[col] = (
            df[col]
            .astype(str)
            .fillna("")
            .apply(lambda x: [v.strip().lower() for v in re.split(r"[,/;&]+", x) if v.strip()] or ["unknown"])
        )

    # Ensure consistent list length
    max_len = df[text_cols].applymap(len).max(axis=1)
    for col in text_cols:
        df[col] = df.apply(
            lambda r: (r[col] + [r[col][-1]] * (max_len[r.name] - len(r[col])))
            if len(r[col]) < max_len[r.name]
            else r[col],
            axis=1
        )

    # Safe explode: expand all text columns simultaneously
    df = df.explode(text_cols, ignore_index=True)

    # Drop rows with meaningless strings
    for col in text_cols:
        df[col] = df[col].replace(["", "unknown", "none", "nan"], pd.NA)
    df = df.dropna(subset=text_cols, how="all")

    # ===========================================================
    # TABS
    # ===========================================================
    all_sets = sorted(set(broods_df["set_label"].dropna().unique().tolist()))
    if not all_sets:
        st.warning("⚠️ No sets found in cached broods — check ETL or database sync.")
        st.stop()

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
    # Prevent type errors
    df["mortality"] = pd.to_numeric(df.get("mortality", 0), errors="coerce").fillna(0).astype(int)

    total_records = len(df)
    total_mortality = df["mortality"].sum()
    unique_mothers = df["mother_id"].nunique()

    # Life expectancy
    df_life = (
        df.groupby("mother_id")["date"]
        .agg(["min", "max"])
        .dropna()
        .assign(days_alive=lambda x: (x["max"] - x["min"]).dt.days)
    )
    avg_life_expectancy = df_life["days_alive"].mean().round(1) if not df_life.empty else 0

    # KPIs
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Records", f"{total_records:,}")
    col2.metric("Unique Mothers", f"{unique_mothers:,}")
    col3.metric("Avg Life Expectancy (days)", f"{avg_life_expectancy}")

    st.divider()

    # Avoid empty chart errors
    if df.empty:
        st.warning("No data available for visualization.")
        return

    # Charts
    def safe_chart(chart_func, title):
        try:
            st.subheader(title)
            chart_func()
        except Exception as e:
            st.error(f"Chart error ({title}): {e}")

    safe_chart(
        lambda: st.altair_chart(
            alt.Chart(df.groupby("date", as_index=False)["mortality"].sum())
            .mark_line(point=True)
            .encode(x="date:T", y="mortality:Q", tooltip=["date", "mortality"])
            .properties(height=300),
            use_container_width=True,
        ),
        "🪦 Mortality Trends Over Time"
    )

    safe_chart(
        lambda: st.altair_chart(
            alt.Chart(df["cause_of_death"].value_counts().reset_index(names=["cause", "count"]))
            .mark_bar()
            .encode(x=alt.X("cause:N", sort="-y"), y="count:Q", color="cause:N")
            .properties(height=300),
            use_container_width=True,
        ),
        "☠️ Distribution of Causes of Death"
    )

    safe_chart(
        lambda: st.altair_chart(
            alt.Chart(df["life_stage"].value_counts().reset_index(names=["life_stage", "count"]))
            .mark_arc(innerRadius=50)
            .encode(theta="count:Q", color="life_stage:N")
            .properties(height=300),
            use_container_width=True,
        ),
        "🦠 Life Stage Distribution"
    )

    safe_chart(
        lambda: st.altair_chart(
            alt.Chart(df["medium_condition"].value_counts().reset_index(names=["medium_condition", "count"]))
            .mark_bar()
            .encode(x=alt.X("medium_condition:N", sort="-y"), y="count:Q", color="medium_condition:N")
            .properties(height=300),
            use_container_width=True,
        ),
        "🌊 Medium Condition Analysis"
    )

    safe_chart(
        lambda: st.altair_chart(
            alt.Chart(df["egg_development"].value_counts().reset_index(names=["egg_development", "count"]))
            .mark_arc(innerRadius=50)
            .encode(theta="count:Q", color="egg_development:N")
            .properties(height=300),
            use_container_width=True,
        ),
        "🥚 Egg Development Status"
    )

    safe_chart(
        lambda: st.altair_chart(
            alt.Chart(
                pd.concat(
                    [
                        df["behavior_pre"].value_counts().rename("count_pre"),
                        df["behavior_post"].value_counts().rename("count_post"),
                    ],
                    axis=1,
                )
                .fillna(0)
                .reset_index(names=["behavior"])
                .melt("behavior", var_name="type", value_name="count")
            )
            .mark_bar()
            .encode(x="behavior:N", y="count:Q", color="type:N")
            .properties(height=300),
            use_container_width=True,
        ),
        "🧠 Behavioral Comparison (Pre vs Post Feeding)"
    )

    safe_chart(
        lambda: st.altair_chart(
            alt.Chart(
                df.groupby("life_stage", as_index=False)["mortality"].mean()
            )
            .mark_bar()
            .encode(x="life_stage:N", y="mortality:Q", color="life_stage:N")
            .properties(height=300),
            use_container_width=True,
        ),
        "⚰️ Mortality by Life Stage"
    )

    st.divider()
    st.subheader("📋 Raw Data Preview")
    st.dataframe(
        df.sort_values("date").reset_index(drop=True),
        use_container_width=True,
        height=400,
    )
