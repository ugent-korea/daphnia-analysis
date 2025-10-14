import re
import pandas as pd
import altair as alt
import streamlit as st
from app.core import database


# ===========================================================
# Helper: Normalize mother_id to canonical format
# ===========================================================
CORE_RE = re.compile(r'^([A-Za-z]+)(.*)$')

def normalize_mother_id(mid: str) -> str:
    """Normalize mother_id to canonical format: LETTER.NUM.NUM_SUFFIX"""
    if not isinstance(mid, str):
        return ""
    
    mid = mid.strip().upper()
    if not mid:
        return ""
    
    # Split core and suffix
    parts = mid.split('_', 1)
    core = parts[0]
    suffix = parts[1] if len(parts) > 1 else ""
    
    # Parse core (e.g., "E.1.2" or "E1.2" or "E12")
    m = CORE_RE.match(core)
    if not m:
        return mid  # Return as-is if pattern doesn't match
    
    word = m.group(1).upper()
    nums = re.findall(r'\d+', m.group(2))
    
    if not nums:
        return mid  # No numbers found, return as-is
    
    # Normalize: remove leading zeros from each number
    nums = [str(int(n)) for n in nums]
    normalized_core = word + '.' + '.'.join(nums)
    
    # Reconstruct with suffix if present
    if suffix:
        return f"{normalized_core}_{suffix}"
    return normalized_core


# ===========================================================
# PAGE: Daphnia Records Analysis (Debug + Clean KPIs)
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
    except Exception as e:
        st.error(f"❌ Failed to load broods cache: {e}")
        return

    # ---- Load cached records ----
    try:
        records = database.get_records()
    except Exception as e:
        st.error(f"❌ Failed to load records table: {e}")
        return

    if records.empty:
        st.warning("⚠️ No records found in the database.")
        st.stop()

    # ---- DEBUG: Show what we loaded ----
    with st.expander("🔍 Debug: Data Loading Info", expanded=False):
        st.write(f"**Loaded {len(broods_df)} broods and {len(records)} records**")
        st.write("**Sample broods (before normalization):**")
        st.dataframe(broods_df[["mother_id", "set_label", "assigned_person"]].head(10))
        st.write("**Sample records (before normalization):**")
        st.dataframe(records[["mother_id", "date"]].head(10))
        
        # Show unique sets in broods
        unique_sets_raw = broods_df["set_label"].dropna().unique()
        st.write(f"**Unique set_labels in broods (raw):** {sorted(unique_sets_raw)}")

    # ---- Normalize IDs using canonical format ----
    records["mother_id_original"] = records["mother_id"]  # Keep original for debugging
    broods_df["mother_id_original"] = broods_df["mother_id"]  # Keep original for debugging
    
    records["mother_id"] = records["mother_id"].map(normalize_mother_id)
    broods_df["mother_id"] = broods_df["mother_id"].map(normalize_mother_id)
    
    # ---- DEBUG: Show normalization results ----
    with st.expander("🔍 Debug: ID Normalization", expanded=False):
        st.write("**Sample normalized IDs:**")
        comparison = pd.DataFrame({
            "Original (broods)": broods_df["mother_id_original"].head(10).values,
            "Normalized (broods)": broods_df["mother_id"].head(10).values,
        })
        st.dataframe(comparison)

    # ---- Merge records ↔ broods (exact like connectivity test) ----
    df = records.merge(broods_df, on="mother_id", how="left", indicator=True)

    # ---- Debug info for mismatches ----
    missing_sets = df[df["_merge"] != "both"].copy()
    if not missing_sets.empty:
        st.warning("⚠️ Some records did not match any broods. Debug info below:")
        st.dataframe(
            missing_sets[["mother_id", "_merge", "set_label", "assigned_person"]].head(20),
            use_container_width=True,
        )

    # check for missing set_labels explicitly
    missing_label = df[df["set_label"].isna()]
    if not missing_label.empty:
        st.info(
            f"ℹ️ {len(missing_label)} records have no set_label assigned after merge. "
            "Displaying a few examples below."
        )
        st.dataframe(missing_label[["mother_id", "date", "mortality"]].head(20))

    # ---- Fill unknowns for visualization ----
    df["set_label"] = df["set_label"].fillna("Unknown")
    broods_df["set_label"] = broods_df["set_label"].fillna("Unknown")

    # ---- Date parsing with multiple format support ----
    def parse_flexible_date(date_str):
        """Parse dates in multiple formats: YYYY-MM-DD, DD-MM-YYYY, MM-DD-YYYY"""
        if pd.isna(date_str) or date_str == "" or date_str is None:
            return pd.NaT
        
        date_str = str(date_str).strip()
        
        # Try multiple formats
        formats = [
            "%Y-%m-%d",      # 2025-10-05
            "%d-%m-%Y",      # 05-10-2025
            "%m-%d-%Y",      # 10-05-2025
            "%Y/%m/%d",      # 2025/10/05
            "%d/%m/%Y",      # 05/10/2025
            "%m/%d/%Y",      # 10/05/2025
        ]
        
        for fmt in formats:
            try:
                return pd.to_datetime(date_str, format=fmt)
            except (ValueError, TypeError):
                continue
        
        # If all formats fail, try pandas auto-detection
        try:
            return pd.to_datetime(date_str, errors='coerce')
        except:
            return pd.NaT
    
    st.write(f"**Before date parsing: {len(df)} records**")
    
    # Apply flexible date parsing
    df["date"] = df["date"].apply(parse_flexible_date)
    
    # Show info about invalid dates
    invalid_dates = df[df["date"].isna()]
    if not invalid_dates.empty:
        st.warning(f"⚠️ Found {len(invalid_dates)} records with unparseable dates.")
        sets_with_invalid_dates = invalid_dates["set_label"].value_counts()
        st.write("**Records with unparseable dates by set:**")
        st.write(sets_with_invalid_dates)
        with st.expander("🔍 Show records with unparseable dates", expanded=False):
            st.dataframe(invalid_dates[["mother_id", "date", "set_label"]].head(20))
    
    # Keep records even with invalid dates, but sort valid ones first
    df = df.sort_values("date", na_position='last')
    st.write(f"**Total records (including {len(invalid_dates)} with invalid dates): {len(df)}**")
    
    df["mortality"] = pd.to_numeric(df.get("mortality", 0), errors="coerce").fillna(0).astype(int)

    # ---- Text cleaning ----
    text_cols = [
        "life_stage", "cause_of_death", "medium_condition",
        "egg_development", "behavior_pre", "behavior_post"
    ]
    for col in text_cols:
        df[col] = df[col].fillna("").astype(str).str.strip().str.lower()

    # ---- Identify sets from BROODS table (not just records) ----
    # Get all sets that exist in broods, regardless of whether they have records
    all_sets_in_broods = sorted(broods_df["set_label"].dropna().unique().tolist())
    # Remove "Unknown" from the list if it exists
    all_sets_in_broods = [s for s in all_sets_in_broods if s != "Unknown"]
    
    if not all_sets_in_broods:
        st.warning("⚠️ No set_label values found in broods table — check broods metadata.")
        st.dataframe(broods_df[["mother_id", "set_label"]].head(20), use_container_width=True)
        st.stop()
    
    # Debug: Show which sets have records
    sets_with_records = sorted(df[df["set_label"] != "Unknown"]["set_label"].dropna().unique().tolist())
    st.info(f"📊 Found {len(all_sets_in_broods)} total sets in broods. Sets with records: {', '.join(sets_with_records) if sets_with_records else 'None yet'}")
    
    all_sets = all_sets_in_broods

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
    unique_mothers = df["mother_id"].nunique()

    df_life = (
        df.groupby("mother_id")["date"]
        .agg(["min", "max"])
        .dropna()
        .assign(days_alive=lambda x: (x["max"] - x["min"]).dt.days)
    )
    avg_life_expectancy = df_life["days_alive"].mean().round(1) if not df_life.empty else 0

    # KPIs (removed Total Mortality)
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Records", f"{total_records:,}")
    c2.metric("Unique Mothers", f"{unique_mothers:,}")
    c3.metric("Avg Life Expectancy (days)", f"{avg_life_expectancy}")

    st.divider()

    # ===================== Charts =====================
    def safe_chart(title, df_builder):
        try:
            result = df_builder()
            if result is None or result[0] is None:
                return
            chart_data, base_df = result
            if isinstance(base_df, pd.DataFrame) and base_df.empty:
                st.info(f"No data for {title}.")
                return
            st.subheader(title)
            st.altair_chart(chart_data, use_container_width=True)
        except Exception as e:
            st.error(f"Chart error ({title}): {e}")

    # Mortality trend
    def trend_chart():
        # Only use records with valid dates for time-series
        t = df[df["date"].notna()].groupby("date", as_index=False)["mortality"].sum()
        if t.empty:
            st.info("No valid dates available for trend chart.")
            return None, t
        chart = (
            alt.Chart(t)
            .mark_line(point=True)
            .encode(x="date:T", y="mortality:Q", tooltip=["date", "mortality"])
            .properties(height=300)
        )
        return chart, t

    # Cause of death
    def cod_chart():
        cod = df["cause_of_death"].value_counts().reset_index()
        cod.columns = ["cause", "count"]
        chart = (
            alt.Chart(cod)
            .mark_bar()
            .encode(x=alt.X("cause:N", sort="-y"), y="count:Q", color="cause:N")
            .properties(height=300)
        )
        return chart, cod

    # Life stage
    def stage_chart():
        s = df["life_stage"].value_counts().reset_index()
        s.columns = ["life_stage", "count"]
        chart = (
            alt.Chart(s)
            .mark_arc(innerRadius=50)
            .encode(theta="count:Q", color="life_stage:N", tooltip=["life_stage", "count"])
            .properties(height=300)
        )
        return chart, s

    # Medium condition
    def medium_chart():
        m = df["medium_condition"].value_counts().reset_index()
        m.columns = ["medium_condition", "count"]
        chart = (
            alt.Chart(m)
            .mark_bar()
            .encode(x=alt.X("medium_condition:N", sort="-y"), y="count:Q", color="medium_condition:N")
            .properties(height=300)
        )
        return chart, m

    # Egg development
    def egg_chart():
        e = df["egg_development"].value_counts().reset_index()
        e.columns = ["egg_development", "count"]
        chart = (
            alt.Chart(e)
            .mark_arc(innerRadius=50)
            .encode(theta="count:Q", color="egg_development:N", tooltip=["egg_development", "count"])
            .properties(height=300)
        )
        return chart, e

    # Behavior comparison
    def behavior_chart():
        pre = df["behavior_pre"].value_counts()
        post = df["behavior_post"].value_counts()
        b = pd.concat([pre.rename("count_pre"), post.rename("count_post")], axis=1).fillna(0)
        b = b.reset_index().rename(columns={"index": "behavior"})
        b = b.melt("behavior", var_name="type", value_name="count")
        chart = (
            alt.Chart(b)
            .mark_bar()
            .encode(x=alt.X("behavior:N", sort="-y"), y="count:Q", color="type:N")
            .properties(height=300)
        )
        return chart, b

    # Mortality by stage
    def mort_stage_chart():
        m = df.groupby("life_stage", as_index=False)["mortality"].mean()
        chart = (
            alt.Chart(m)
            .mark_bar()
            .encode(x=alt.X("life_stage:N", sort="-y"), y="mortality:Q", color="life_stage:N")
            .properties(height=300)
        )
        return chart, m

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
