import pandas as pd
import streamlit as st
from app.core import database, utils, visualizations


def render():
    """Main render function for Daphnia Records Analysis page."""
    st.title("📊 Daphnia Records Analysis")
    st.caption("Automated analysis of Daphnia mortality, environment, and behavior trends")

    # Load data
    try:
        broods_df, records_df, current_df = _load_and_validate_data()
    except Exception as e:
        st.error(f"❌ Failed to load data: {e}")
        return
    
    # Check for invalid status entries and show warning
    _render_invalid_status_warning()

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
    _render_analysis_tabs(df, broods_df, current_df, all_sets)


def _load_and_validate_data():
    """Load broods, records, and current data from database."""
    # Load broods
    data = database.get_data()
    by_full = data.get("by_full", {})
    broods_df = pd.DataFrame.from_dict(by_full, orient="index")
    if "mother_id" not in broods_df.columns:
        broods_df["mother_id"] = broods_df.index
    
    # Load records
    records_df = database.get_records()
    
    # Load current (alive broods)
    try:
        current_df = database.get_current()
    except Exception as e:
        st.warning(f"⚠️ Current table not yet available: {e}")
        current_df = pd.DataFrame()
    
    return broods_df, records_df, current_df


def _render_invalid_status_warning():
    """Display warning for invalid status entries."""
    try:
        data = database.get_data()
        meta = data.get("meta", {})
        invalid_status_raw = meta.get('invalid_status_entries')
        
        if invalid_status_raw:
            try:
                import ast
                invalid_entries = ast.literal_eval(invalid_status_raw)
                if invalid_entries:
                    st.error(f"⚠️ **DATA QUALITY ALERT: {len(invalid_entries)} brood(s) have invalid status entries!**")
                    
                    with st.expander("📋 View Invalid Status Entries", expanded=False):
                        st.warning(
                            "**Status must be ONLY:** `Alive` or `Dead` (case-insensitive)\n\n"
                            "**Invalid entries found:**"
                        )
                        
                        # Group by assigned person
                        from collections import defaultdict
                        by_person = defaultdict(list)
                        for entry in invalid_entries:
                            person = entry.get('assigned_person', 'Unknown')
                            by_person[person].append(entry)
                        
                        for person, entries in sorted(by_person.items()):
                            st.markdown(f"**👤 {person}** ({len(entries)} entries)")
                            for entry in entries:
                                st.markdown(
                                    f"- Mother ID: `{entry['mother_id']}` | "
                                    f"Set: {entry['set_label']} | "
                                    f"Invalid Status: `{entry['status']}`"
                                )
                        
                        st.info("💡 **Action Required:** Update Google Sheets to use only 'Alive' or 'Dead', then run ETL refresh.")
            except Exception as e:
                st.error(f"Error parsing invalid status entries: {e}")
    except Exception:
        pass  # Silently skip if meta not available


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


def _render_analysis_tabs(df: pd.DataFrame, broods_df: pd.DataFrame, current_df: pd.DataFrame, all_sets: list):
    """Render tabs for cumulative and individual set analysis."""
    tabs = st.tabs(["🌍 Cumulative"] + [f"Set {s}" for s in all_sets])

    for i, tab in enumerate(tabs):
        with tab:
            if i == 0:
                # Cumulative tab
                df_sub = df
                current_sub = current_df
                assigned_person = "All Researchers"
                st.markdown("### 🌍 Cumulative Overview (All Sets Combined)")
                _render_dashboard(df_sub, current_sub, broods_df, "Cumulative")
            else:
                # Individual set tab
                set_name = all_sets[i - 1]
                df_sub = df[df["set_label"] == set_name]
                current_sub = current_df[current_df["set_label"] == set_name] if not current_df.empty else pd.DataFrame()
                assigned_person = _get_assigned_person(broods_df, set_name)
                
                st.markdown(f"### 🧬 Set {set_name} Overview")
                st.caption(f"👩 Assigned to: **{assigned_person}**")
                
                if df_sub.empty:
                    st.info("⚠️ No records logged for this set yet.")
                else:
                    _render_dashboard(df_sub, current_sub, broods_df, set_name)


def _get_assigned_person(broods_df: pd.DataFrame, set_name: str) -> str:
    """Get assigned person for a specific set."""
    assigned_person = (
        broods_df.loc[broods_df["set_label"] == set_name, "assigned_person"]
        .dropna()
        .unique()
    )
    return assigned_person[0] if len(assigned_person) > 0 else "Unassigned"


def _render_dashboard(df: pd.DataFrame, current_df: pd.DataFrame, broods_df: pd.DataFrame, set_name: str):
    """Render complete dashboard for a dataset."""
    # Filter broods_df by set if not cumulative
    if set_name != "Cumulative":
        broods_df_filtered = broods_df[broods_df["set_label"] == set_name]
    else:
        broods_df_filtered = broods_df
    
    # Calculate and display metrics
    metrics = utils.calculate_metrics(df, current_df, broods_df_filtered)
    _render_kpis(metrics)
    
    # Render life stage breakdown (second row of cards) - pass broods_df_filtered
    _render_life_stage_cards(current_df, broods_df_filtered)
    
    st.divider()
    
    # Render all charts - pass filtered broods
    _render_all_charts(df, broods_df_filtered)
    
    st.divider()
    
    # Show data quality info if there are issues
    _render_data_quality_info(df)
    
    # Raw data preview
    _render_raw_data_preview(df)


def _render_kpis(metrics: dict):
    """Render KPI metrics in columns."""
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Records", f"{metrics['total_records']:,}")
    c2.metric("Unique Mothers", f"{metrics['unique_mothers']:,}")
    c3.metric("Alive Broods", f"{metrics['active_broods']:,}")
    
    # Average life expectancy
    avg_life_exp = metrics.get('avg_life_expectancy')
    if avg_life_exp is not None and avg_life_exp > 0:
        c4.metric("Avg Brood Life Expectancy", f"{avg_life_exp:.1f} days")
    else:
        c4.metric("Avg Brood Life Expectancy", "N/A")


def _render_life_stage_cards(current_df: pd.DataFrame, broods_df: pd.DataFrame):
    """
    Render life stage breakdown cards for alive broods.
    
    Data source: The `current` table contains the most recent record for each alive brood.
    This table is materialized by refresh_current.py ETL script which:
    1. Queries broods table for alive mothers (no death_date, status != dead)
    2. Joins with records table to get the latest record (by date) for each alive mother
    3. Stores in the `current` table with columns including life_stage
    
    This function sums the n_i (initial population) values from the broods table
    for each life stage category, providing the total initial population by life stage.
    
    IMPORTANT: We only count n_i for broods that exist in the current table.
    """
    if current_df.empty:
        st.info("⚠️ No alive broods data available yet")
        return
    
    # Merge current_df with broods_df to get n_i values alongside life_stage
    merged = current_df.merge(
        broods_df[["mother_id", "n_i"]], 
        on="mother_id", 
        how="left"
    )
    
    # Normalize life_stage values
    merged["life_stage_clean"] = merged["life_stage"].fillna("").str.strip().str.lower()
    
    # Sum n_i (initial population) for each life stage
    # Note: Handle both "adolescent" and "adolescence"
    adults_n_i = merged[merged["life_stage_clean"] == "adult"]["n_i"].fillna(0).sum()
    adolescents_n_i = merged[
        (merged["life_stage_clean"] == "adolescent") | 
        (merged["life_stage_clean"] == "adolescence")
    ]["n_i"].fillna(0).sum()
    neonates_n_i = merged[merged["life_stage_clean"] == "neonate"]["n_i"].fillna(0).sum()
    
    # Calculate total initial population (should equal sum of above if all broods have valid life_stage)
    total_initial_pop = merged["n_i"].fillna(0).sum()
    
    st.markdown("#### Current number of daphnias by life stage")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🟢 Adults", f"{int(adults_n_i):,}")
    c2.metric("🟡 Adolescents", f"{int(adolescents_n_i):,}")
    c3.metric("🔵 Neonates", f"{int(neonates_n_i):,}")
    c4.metric("👥 Total", f"{int(total_initial_pop):,}")


def _render_all_charts(df: pd.DataFrame, broods_df: pd.DataFrame):
    """Render all analysis charts using the visualizations module."""
    # First, render the life expectancy distribution chart for dead broods
    _render_life_expectancy_distribution(df, broods_df)
    
    # Then render all other charts
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


def _render_life_expectancy_distribution(df: pd.DataFrame, broods_df: pd.DataFrame):
    """Render life expectancy distribution chart for dead broods."""
    import altair as alt
    
    st.subheader("📊 Life Expectancy Distribution (Dead Broods)")
    
    # Filter for dead broods using regex pattern (case-insensitive, whitespace-trimmed)
    dead_broods = broods_df[
        broods_df["status"].astype(str).str.strip().str.lower().str.match(r'^dead$', na=False)
    ].copy()
    
    if dead_broods.empty:
        st.info("📊 No dead broods found yet - life expectancy data will appear here once broods complete their lifecycle")
        return
    
    # Parse birth and death dates (death_date might be 'Unknown' or NULL)
    dead_broods["birth_date_parsed"] = dead_broods["birth_date"].apply(utils.parse_date_safe)
    dead_broods["death_date_parsed"] = dead_broods["death_date"].apply(utils.parse_date_safe)
    
    # Calculate life expectancy in days
    dead_broods["life_expectancy_days"] = (
        dead_broods["death_date_parsed"] - dead_broods["birth_date_parsed"]
    ).dt.days
    
    # Filter out invalid calculations (including Unknown death dates)
    dead_broods_valid = dead_broods[
        (dead_broods["life_expectancy_days"].notna()) &
        (dead_broods["life_expectancy_days"] >= 0)
    ].copy()
    
    if dead_broods_valid.empty:
        st.warning(f"⚠️ Found {len(dead_broods)} dead broods, but could not calculate life expectancy - check birth/death date formats (death_date cannot be 'Unknown' for calculation)")
        return
    
    # Show statistics FIRST (before the chart)
    col1, col2, col3 = st.columns(3)
    col1.metric("Dead Broods", f"{len(dead_broods_valid):,}")
    col2.metric("Avg Life Expectancy", f"{dead_broods_valid['life_expectancy_days'].mean():.1f} days")
    col3.metric("Max Life Expectancy", f"{dead_broods_valid['life_expectancy_days'].max():.0f} days")
    
    # Create histogram AFTER the cards
    chart = alt.Chart(dead_broods_valid).mark_bar(
        opacity=0.7,
        color="#4CAF50"
    ).encode(
        x=alt.X(
            "life_expectancy_days:Q",
            bin=alt.Bin(maxbins=20),
            title="Life Expectancy (days)"
        ),
        y=alt.Y(
            "count()",
            title="Number of Broods"
        ),
        tooltip=[
            alt.Tooltip("life_expectancy_days:Q", bin=True, title="Days"),
            alt.Tooltip("count()", title="Count")
        ]
    ).properties(
        height=300
    )
    
    st.altair_chart(chart, use_container_width=True)
