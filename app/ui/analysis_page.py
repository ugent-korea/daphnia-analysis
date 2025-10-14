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

    # ---- Optional: Advanced Debug Info ----
    with st.expander("🔧 Advanced Debug Info (Click to expand)", expanded=False):
        st.write(f"**Loaded {len(broods_df)} broods and {len(records)} records**")
        st.write("**Sample broods (before normalization):**")
        st.dataframe(broods_df[["mother_id", "set_label", "assigned_person"]].head(10))
        st.write("**Sample records (before normalization):**")
        st.dataframe(records[["mother_id", "date"]].head(10))
        
        # Show unique sets in broods
        unique_sets_raw = broods_df["set_label"].dropna().unique()
        st.write(f"**Unique set_labels in broods (raw):** {sorted(unique_sets_raw)}")
        
        # Show normalization
        st.write("**Sample normalized IDs:**")
        comparison = pd.DataFrame({
            "Original (broods)": broods_df["mother_id_original"].head(10).values,
            "Normalized (broods)": broods_df["mother_id"].head(10).values,
        })
        st.dataframe(comparison)

    # ---- Normalize IDs using canonical format ----
    records["mother_id_original"] = records["mother_id"]  # Keep original for debugging
    broods_df["mother_id_original"] = broods_df["mother_id"]  # Keep original for debugging
    
    records["mother_id"] = records["mother_id"].map(normalize_mother_id)
    broods_df["mother_id"] = broods_df["mother_id"].map(normalize_mother_id)

    # ---- Merge records ↔ broods ----
    df = records.merge(broods_df, on="mother_id", how="left", indicator=True)

    # ---- Check for merge issues (only show if problems exist) ----
    missing_sets = df[df["_merge"] != "both"].copy()
    if not missing_sets.empty:
        with st.expander("⚠️ Data Merge Warning - Click to see details", expanded=False):
            st.warning(f"Found {len(missing_sets)} records that did not match any broods.")
            st.dataframe(
                missing_sets[["mother_id", "_merge", "set_label", "assigned_person"]].head(20),
                use_container_width=True,
            )

    # ---- Fill unknowns for visualization ----
    df["set_label"] = df["set_label"].fillna("Unknown")
    broods_df["set_label"] = broods_df["set_label"].fillna("Unknown")

    # ---- Date parsing - handle NULL/empty dates gracefully ----
    def parse_date_safe(date_val):
        """Parse date, return NaT for NULL/empty values"""
        if pd.isna(date_val) or date_val == "" or date_val is None:
            return pd.NaT
        
        date_str = str(date_val).strip()
        if date_str.upper() in ["NULL", "NA", "N/A", "NONE", ""]:
            return pd.NaT
        
        # Try pandas auto-detection (handles YYYY-MM-DD, DD-MM-YYYY, etc.)
        try:
            return pd.to_datetime(date_str, errors='coerce')
        except:
            return pd.NaT
    
    # Apply date parsing
    df["date"] = df["date"].apply(parse_date_safe)
    
    # Store debug info for later (show at bottom if needed)
    records_without_dates = df[df["date"].isna()]
    debug_info = {
        "total_records": len(df),
        "records_with_dates": df['date'].notna().sum(),
        "records_without_dates": len(records_without_dates),
        "sets_without_dates": records_without_dates["set_label"].value_counts() if not records_without_dates.empty else None
    }
    
    # Keep ALL records, sort by date (NaT goes to end)
    df = df.sort_values("date", na_position='last')
    
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
                show_dashboard(df_sub, set_name if i > 0 else "Cumulative")


# ===========================================================
# DASHBOARD COMPONENT
# ===========================================================
def show_dashboard(df, set_name=""):
    total_records = len(df)
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
    def safe_chart(title, df_builder):
        """Safely render a chart, showing user-friendly error if it fails"""
        try:
            result = df_builder()
            if result is None or result[0] is None:
                return
            chart_data, base_df = result
            if isinstance(base_df, pd.DataFrame) and base_df.empty:
                st.info(f"📊 {title}: No data available")
                return
            st.subheader(title)
            st.altair_chart(chart_data, use_container_width=True)
        except Exception as e:
            st.warning(f"📊 {title}: Unable to display chart (data format issue)")
            # Only show technical details in expander
            with st.expander("🔧 Technical details", expanded=False):
                st.code(str(e))

    # Mortality trend
    def trend_chart():
        # Only use records with valid dates for time-series
        t = df[df["date"].notna()].groupby("date", as_index=False)["mortality"].sum()
        if t.empty:
            return None, t  # Return None to trigger "No data available" message
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
    
    # ===================== Debug Info (only if there are issues) =====================
    records_without_dates = df[df["date"].isna()]
    has_issues = not records_without_dates.empty
    
    if has_issues:
        with st.expander("🔍 Data Quality Info", expanded=False):
            st.markdown("#### Records Without Dates")
            st.write(f"Found **{len(records_without_dates)}** records with missing dates in this set.")
            st.caption("These records are included in non-time-series charts but excluded from trend analysis.")
            st.dataframe(
                records_without_dates[["mother_id", "date", "life_stage", "mortality"]].head(10),
                use_container_width=True
            )
    
    # ===================== Raw Data Preview =====================
    st.subheader("📋 Raw Data Preview")
    st.dataframe(df.sort_values("date", na_position='last').reset_index(drop=True), use_container_width=True, height=400)
