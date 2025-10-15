import streamlit as st
import pandas as pd
from app.core import database, utils


def render():
    """Test connectivity between records and broods tables."""
    st.title("🧩 Daphnia Records Connection Test")
    st.caption("Verifying if records correctly connect to broods (per-set isolation with error capture)")

    # Load data
    try:
        broods_df, records_df = _load_and_validate_data()
    except Exception as e:
        st.error(f"❌ Failed to load data: {e}")
        return

    if records_df.empty:
        st.warning("⚠️ No records found in the database.")
        st.stop()

    # Prepare data using shared utilities
    df = utils.prepare_analysis_data(records_df, broods_df)
    
    # Ensure set_label exists after preparation
    if "set_label" not in df.columns:
        st.error("❌ 'set_label' column not found after data preparation. Available columns: " + ", ".join(df.columns))
        st.dataframe(df.head())
        return

    # Display overview
    _render_overview(records_df, broods_df, df)

    # Get all unique sets from broods table (safer to use broods_df directly)
    all_sets = _get_all_sets_from_broods(broods_df)
    
    if not all_sets:
        st.warning("⚠️ No set_label values found in broods table — check broods metadata.")
        st.dataframe(broods_df[["mother_id", "set_label"]].head(20), use_container_width=True)
        st.stop()

    # Render tabs for individual sets (no cumulative)
    _render_set_tabs(df, broods_df, all_sets)


def _load_and_validate_data():
    """Load broods and records data from database."""
    # Load broods
    data = database.get_data()
    by_full = data.get("by_full", {})
    broods_df = pd.DataFrame.from_dict(by_full, orient="index")
    if "mother_id" not in broods_df.columns:
        broods_df["mother_id"] = broods_df.index
    
    # Ensure set_label column exists in broods
    if "set_label" not in broods_df.columns:
        st.error("❌ 'set_label' column not found in broods table")
        st.write("Available columns:", list(broods_df.columns))
        st.stop()
    
    # Load records
    records_df = database.get_records()
    
    return broods_df, records_df


def _render_overview(records_df: pd.DataFrame, broods_df: pd.DataFrame, merged_df: pd.DataFrame):
    """Display overview statistics."""
    st.info(f"✅ Loaded {len(records_df):,} records | {len(broods_df):,} broods")
    
    with st.expander("🔍 Data Structure Info", expanded=False):
        st.write(f"**Merged dataframe columns:** {', '.join(merged_df.columns)}")
        st.write(f"**Broods columns:** {', '.join(broods_df.columns)}")
        st.write(f"**Records columns:** {', '.join(records_df.columns)}")
        
        # Show merge quality
        if "_merge" in merged_df.columns:
            merge_stats = merged_df["_merge"].value_counts()
            st.write("**Merge Statistics:**")
            st.write(merge_stats)


def _get_all_sets_from_broods(broods_df: pd.DataFrame) -> list:
    """Get all unique set labels from broods table."""
    if "set_label" not in broods_df.columns:
        return []
    
    all_sets = sorted(broods_df["set_label"].dropna().unique().tolist())
    # Remove "Unknown" from the list if it exists
    all_sets = [s for s in all_sets if s != "Unknown"]
    return all_sets


def _render_set_tabs(df: pd.DataFrame, broods_df: pd.DataFrame, all_sets: list):
    """Render tabs for individual set connectivity testing."""
    tabs = st.tabs([f"Set {s}" for s in all_sets])

    for i, tab in enumerate(tabs):
        with tab:
            try:
                set_name = all_sets[i]
                _render_set_connectivity(df, broods_df, set_name)
            except Exception as e:
                # Catch any tab-specific failure
                st.error(f"❌ Error while loading Set {all_sets[i]}: {type(e).__name__} — {e}")
                with st.expander("Full error details"):
                    st.exception(e)


def _render_set_connectivity(df: pd.DataFrame, broods_df: pd.DataFrame, set_name: str):
    """Render connectivity test for a specific set."""
    st.markdown(f"### 🧬 Set {set_name} Connectivity Test")
    
    # Verify set_label column exists
    if "set_label" not in df.columns:
        st.error(f"❌ Cannot filter by set: 'set_label' column not found in merged data")
        st.write("Available columns:", list(df.columns))
        return
    
    # Filter data for this set
    subset = df[df["set_label"] == set_name].copy()
    
    if subset.empty:
        st.warning(f"⚠️ No records found for Set {set_name}.")
        return
    
    # Get assigned person
    assigned_person = (
        broods_df.loc[broods_df["set_label"] == set_name, "assigned_person"]
        .dropna()
        .unique()
    )
    person = assigned_person[0] if len(assigned_person) > 0 else "Unassigned"
    st.caption(f"👩 Assigned to: **{person}**")
    
    # Display statistics
    unique_mothers = subset["mother_id"].nunique()
    total_records = len(subset)
    
    st.success(
        f"✅ Found **{total_records:,} records** "
        f"from **{unique_mothers:,} unique mothers**."
    )
    
    # Check for connection issues
    _check_connection_quality(subset)
    
    # Display sample data
    st.subheader("📋 Sample Records")
    display_cols = [c for c in ["mother_id", "set_label", "date", "life_stage", 
                                  "mortality", "cause_of_death", "assigned_person"] 
                    if c in subset.columns]
    
    if display_cols:
        st.dataframe(
            subset[display_cols].head(20),
            use_container_width=True,
        )
    else:
        st.warning("⚠️ Expected columns not found in subset")
        st.dataframe(subset.head(20), use_container_width=True)
    
    # Display connection statistics
    _render_connection_stats(subset)


def _check_connection_quality(subset: pd.DataFrame):
    """Check and report connection quality issues."""
    if "_merge" not in subset.columns:
        return
    
    unmatched = subset[subset["_merge"] != "both"]
    if not unmatched.empty:
        st.warning(
            f"⚠️ Found {len(unmatched)} records that didn't match any broods. "
            f"This may indicate data quality issues."
        )
        with st.expander("View unmatched records"):
            display_cols = [c for c in ["mother_id", "_merge", "set_label"] if c in unmatched.columns]
            if display_cols:
                st.dataframe(
                    unmatched[display_cols].head(10),
                    use_container_width=True
                )
            else:
                st.dataframe(unmatched.head(10), use_container_width=True)


def _render_connection_stats(subset: pd.DataFrame):
    """Render detailed connection statistics."""
    st.subheader("📊 Connection Statistics")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Records", f"{len(subset):,}")
    
    with col2:
        st.metric("Unique Mothers", f"{subset['mother_id'].nunique():,}")
    
    with col3:
        if "date" in subset.columns:
            records_with_dates = subset["date"].notna().sum()
            st.metric("Records with Dates", f"{records_with_dates:,}")
        else:
            st.metric("Records with Dates", "N/A")
    
    # Show distribution by life stage
    if "life_stage" in subset.columns:
        st.write("**Distribution by Life Stage:**")
        life_stage_dist = subset["life_stage"].value_counts()
        if not life_stage_dist.empty:
            st.dataframe(life_stage_dist.reset_index(), use_container_width=True)
        else:
            st.write("No life stage data available")
