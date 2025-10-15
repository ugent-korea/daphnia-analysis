import pandas as pd
import streamlit as st
from app.core import database, utils, visualizations


def render():
    """Main render function for Daphnia Records Analysis page."""
    st.title("📊 Daphnia Records Analysis")
    st.caption("Automated analysis of Daphnia mortality, environment, and behavior trends")

    # Load data
    try:
        broods_df, records_df = _load_and_validate_data()
    except Exception as e:
        st.error(f"❌ Failed to load data: {e}")
        return

    if records_df.empty:
        st.warning("⚠️ No records found in the database.")
        st.stop()

    # Debug info (collapsed by default)
    # _render_debug_panel(broods_df, records_df)

    # Prepare data for analysis
    df = utils.prepare_analysis_data(records_df, broods_df)

    # Check for merge issues
    _render_merge_warnings(df)

    # Get all unique sets from broods table
    all_sets = _get_all_sets_from_broods(broods_df)
    
    if not all_sets:
        st.warning("⚠️ No set_label values found in broods table — check broods metadata.")
        st.dataframe(broods_df[["mother_id", "set_label"]].head(20), use_container_width=True)
        st.stop()

    # Render tabs for cumulative and individual sets
    _render_analysis_tabs(df, broods_df, all_sets)


def _load_and_validate_data():
    """Load broods and records data from database."""
    # Load broods
    data = database.get_data()
    by_full = data.get("by_full", {})
    broods_df = pd.DataFrame.from_dict(by_full, orient="index")
    if "mother_id" not in broods_df.columns:
        broods_df["mother_id"] = broods_df.index
    
    # Load records
    records_df = database.get_records()
    
    return broods_df, records_df


def _render_debug_panel(broods_df: pd.DataFrame, records_df: pd.DataFrame):
    """Render collapsible debug information panel."""
    with st.expander("🔧 Advanced Debug Info (Click to expand)", expanded=False):
        st.write(f"**Loaded {len(broods_df)} broods and {len(records_df)} records**")
        
        st.write("**Columns in broods_df:**", list(broods_df.columns))
        st.write("**Columns in records:**", list(records_df.columns))
        
        st.write("**Sample broods:**")
        if "set_label" in broods_df.columns and "assigned_person" in broods_df.columns:
            st.dataframe(broods_df[["mother_id", "set_label", "assigned_person"]].head(10))
        else:
            st.dataframe(broods_df.head(10))
            
        st.write("**Sample records:**")
        cols_to_show = [c for c in ["mother_id", "date", "set_label", "assigned_person"] if c in records_df.columns]
        if cols_to_show:
            st.dataframe(records_df[cols_to_show].head(10))
        else:
            st.dataframe(records_df.head(10))


def _render_merge_warnings(df: pd.DataFrame):
    """Display warnings for records that didn't match broods."""
    if "_merge" not in df.columns:
        return
    
    missing_sets = df[df["_merge"] != "both"].copy()
    if not missing_sets.empty:
        with st.expander("⚠️ Data Merge Warning - Click to see details", expanded=False):
            st.warning(f"Found {len(missing_sets)} records that did not match any broods.")
            st.dataframe(
                missing_sets[["mother_id", "_merge", "set_label", "assigned_person"]].head(20),
                use_container_width=True,
            )


def _get_all_sets_from_broods(broods_df: pd.DataFrame) -> list:
    """Get all unique set labels from broods table."""
    all_sets = sorted(broods_df["set_label"].dropna().unique().tolist())
    # Remove "Unknown" from the list if it exists
    all_sets = [s for s in all_sets if s != "Unknown"]
    return all_sets


def _render_analysis_tabs(df: pd.DataFrame, broods_df: pd.DataFrame, all_sets: list):
    """Render tabs for cumulative and individual set analysis."""
    tabs = st.tabs(["🌍 Cumulative"] + [f"Set {s}" for s in all_sets])

    for i, tab in enumerate(tabs):
        with tab:
            if i == 0:
                # Cumulative tab
                df_sub = df
                assigned_person = "All Researchers"
                st.markdown("### 🌍 Cumulative Overview (All Sets Combined)")
                _render_dashboard(df_sub, "Cumulative")
            else:
                # Individual set tab
                set_name = all_sets[i - 1]
                df_sub = df[df["set_label"] == set_name]
                assigned_person = _get_assigned_person(broods_df, set_name)
                
                st.markdown(f"### 🧬 Set {set_name} Overview")
                st.caption(f"👩 Assigned to: **{assigned_person}**")
                
                if df_sub.empty:
                    st.info("⚠️ No records logged for this set yet.")
                else:
                    _render_dashboard(df_sub, set_name)


def _get_assigned_person(broods_df: pd.DataFrame, set_name: str) -> str:
    """Get assigned person for a specific set."""
    assigned_person = (
        broods_df.loc[broods_df["set_label"] == set_name, "assigned_person"]
        .dropna()
        .unique()
    )
    return assigned_person[0] if len(assigned_person) > 0 else "Unassigned"


def _render_dashboard(df: pd.DataFrame, set_name: str):
    """Render complete dashboard for a dataset."""
    # Calculate and display metrics
    metrics = utils.calculate_metrics(df)
    _render_kpis(metrics)
    
    st.divider()
    
    # Render all charts
    _render_all_charts(df)
    
    st.divider()
    
    # Show data quality info if there are issues
    _render_data_quality_info(df)
    
    # Raw data preview
    _render_raw_data_preview(df)


def _render_kpis(metrics: dict):
    """Render KPI metrics in columns."""
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Records", f"{metrics['total_records']:,}")
    c2.metric("Unique Mothers", f"{metrics['unique_mothers']:,}")
    c3.metric("Avg Life Expectancy (days)", f"{metrics['avg_life_expectancy']}")


def _render_all_charts(df: pd.DataFrame):
    """Render all analysis charts using the visualizations module."""
    for chart_def in visualizations.CHART_DEFINITIONS:
        _render_safe_chart(
            title=chart_def["title"],
            builder=chart_def["builder"],
            df=df
        )


def _render_safe_chart(title: str, builder, df: pd.DataFrame):
    """Safely render a chart with error handling."""
    try:
        result = builder(df)
        if result is None:
            st.info(f"📊 {title}: No data available")
            return
        
        chart, data = result
        if isinstance(data, pd.DataFrame) and data.empty:
            st.info(f"📊 {title}: No data available")
            return
        
        st.subheader(title)
        st.altair_chart(chart, use_container_width=True)
    except Exception as e:
        st.warning(f"📊 {title}: Unable to display chart (data format issue)")
        with st.expander("🔧 Technical details", expanded=False):
            st.code(str(e))


def _render_data_quality_info(df: pd.DataFrame):
    """Render data quality information if there are issues."""
    records_without_dates = df[df["date"].isna()]
    
    if not records_without_dates.empty:
        with st.expander("🔍 Data Quality Info", expanded=False):
            st.markdown("#### Records Without Dates")
            st.write(f"Found **{len(records_without_dates)}** records with missing dates in this set.")
            st.caption("These records are included in non-time-series charts but excluded from trend analysis.")
            st.dataframe(
                records_without_dates[["mother_id", "date", "life_stage", "mortality"]].head(10),
                use_container_width=True
            )


def _render_raw_data_preview(df: pd.DataFrame):
    """Render raw data preview table."""
    st.subheader("📋 Raw Data Preview")
    st.dataframe(
        df.sort_values("date", na_position='last').reset_index(drop=True), 
        use_container_width=True, 
        height=400
    )
