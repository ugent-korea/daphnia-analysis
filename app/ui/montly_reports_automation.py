"""
Dynamic monthly analytics dashboard that supports multiple months.
Automatically detects available months from database and generates reports.
"""

from dataclasses import dataclass
from typing import List
from datetime import datetime
from calendar import month_name

import pandas as pd
import streamlit as st

from app.core import monthly_analytics, report_generator
from app.ui.monthly_reports import (
    _filter_broods_by_month,
    _load_data,
    _render_demographics_section,
    _render_mortality_section,
    _render_reproduction_section,
    _render_egg_production_section,
    _render_life_stage_and_reproduction_timing,
    _render_survival_analysis_section,
)


@dataclass(frozen=True)
class MonthConfig:
    """Configuration for a specific monthly report."""

    label: str
    year: int
    month: int


def _get_month_configs(records_df: pd.DataFrame) -> List[MonthConfig]:
    """
    Automatically detect available months from database.
    Returns list of months that have data, sorted chronologically.
    """
    if records_df.empty:
        return []
    
    # Parse dates
    records_df = records_df.copy()
    records_df['date_parsed'] = records_df['date'].apply(monthly_analytics.parse_date_safe)
    records_df = records_df[records_df['date_parsed'].notna()]
    
    if records_df.empty:
        return []
    
    # Get unique year-month combinations
    records_df['year'] = records_df['date_parsed'].dt.year
    records_df['month'] = records_df['date_parsed'].dt.month
    
    unique_months = records_df[['year', 'month']].drop_duplicates().sort_values(['year', 'month'])
    
    # Create MonthConfig for each unique month
    configs = []
    for _, row in unique_months.iterrows():
        year = int(row['year'])
        month = int(row['month'])
        label = f"{month_name[month]} {year}"
        configs.append(MonthConfig(label, year, month))
    
    return configs


def _get_default_month_index(configs: List[MonthConfig]) -> int:
    """
    Determine default month to display.
    Returns index of previous month (for end-of-month reporting).
    If previous month not available, returns latest available month.
    """
    if not configs:
        return 0
    
    now = datetime.now()
    current_year = now.year
    current_month = now.month
    
    # Calculate previous month
    if current_month == 1:
        prev_month = 12
        prev_year = current_year - 1
    else:
        prev_month = current_month - 1
        prev_year = current_year
    
    # Try to find previous month in configs
    for idx, config in enumerate(configs):
        if config.year == prev_year and config.month == prev_month:
            return idx
    
    # If previous month not found, return latest month
    return len(configs) - 1


def render():
    """Main render function for dynamic Monthly Reports page."""
    st.title("📅 Monthly Analytics Reports")
    st.caption("Comprehensive end-of-month analysis of Daphnia breeding experiments")

    try:
        broods_df, records_df = _load_data()
    except Exception as e:
        st.error(f"Failed to load data: {e}")
        return

    if records_df.empty:
        st.warning("No records found in the database.")
        return

    # Auto-detect available months from database
    month_configs = _get_month_configs(records_df)
    
    if not month_configs:
        st.warning("No months with data found in the database.")
        return
    
    st.divider()
    
    # Get default month (previous month for end-of-month reporting)
    default_index = _get_default_month_index(month_configs)
    
    # Month selector as proper dropdown (not editable)
    # Add CSS to prevent any text editing
    st.markdown("""
        <style>
        /* Ensure selectbox is not editable */
        div[data-baseweb="select"] input {
            pointer-events: none !important;
            cursor: default !important;
        }
        /* Style the select container */
        div[data-baseweb="select"] > div {
            cursor: pointer !important;
        }
        </style>
    """, unsafe_allow_html=True)
    
    month_options = [cfg.label for cfg in month_configs]
    
    selected_label = st.selectbox(
        "📊 Select report month:",
        options=month_options,
        index=default_index,
        help="Select a month to view its detailed analytics report",
        disabled=False,
        label_visibility="visible"
    )
    
    selected_config = next(cfg for cfg in month_configs if cfg.label == selected_label)

    st.divider()

    # Filter records strictly for the selected month
    month_records = monthly_analytics.filter_records_by_month(
        records_df, selected_config.year, selected_config.month
    )
    month_broods = _filter_broods_by_month(
        broods_df, selected_config.year, selected_config.month
    )

    if month_records.empty:
        st.info(f"No records found for {selected_label}")
        return

    _render_month_dashboard(month_records, month_broods, broods_df, selected_label)


def _render_month_dashboard(
    month_records: pd.DataFrame,
    month_broods: pd.DataFrame,
    all_broods_df: pd.DataFrame,
    month_label: str,
):
    """Render the complete dashboard for a given month."""

    tabs = st.tabs(
        [
            "Summary Report",
            "Demographics",
            "Mortality Analysis",
            "Reproduction Metrics",
            "Egg Production Analysis",
            "Life Stage & Reproduction Timing",
            "Survival Analysis",
        ]
    )

    with tabs[0]:
        _render_summary(month_records, month_broods, month_label)

    with tabs[1]:
        _render_demographics_section(month_records, month_broods)

    with tabs[2]:
        _render_mortality_section(month_records)

    with tabs[3]:
        _render_reproduction_section(month_records, month_broods)

    with tabs[4]:
        _render_egg_production_section(month_records, month_broods)

    with tabs[5]:
        _render_life_stage_and_reproduction_timing(month_records)

    with tabs[6]:
        _render_survival_analysis_section(month_broods)


def _render_summary(month_records: pd.DataFrame, month_broods: pd.DataFrame, month_label: str):
    """Render executive summary with auto-generated narrative report."""
    st.subheader(f"Executive Summary - {month_label}")

    demo = monthly_analytics.calculate_demographics(month_records, month_broods)
    mort = monthly_analytics.calculate_mortality_rates(month_records)
    repro = monthly_analytics.calculate_reproduction_metrics(month_records, month_broods)
    trans = monthly_analytics.calculate_life_stage_transitions(month_records)
    timing = monthly_analytics.calculate_reproduction_timing_v2(month_records)

    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Population", f"{demo['total_records']:,}")
    col2.metric("Active Mothers", f"{demo['unique_mothers']:,}")
    col3.metric("Neonates Born", f"{repro['brood_size']['total_neonates']:,}")

    total_deaths = sum(stage['sum'] for stage in mort.values()) if mort else 0
    col4.metric("Total Deaths", f"{int(total_deaths):,}")

    st.divider()

    # Auto-generated narrative report
    narrative = report_generator.generate_executive_summary(
        demo, mort, repro, trans, month_label
    )
    st.markdown(narrative)
    
    st.divider()
    
    # Auto-generated key findings
    findings = report_generator.generate_key_findings()
    st.success(findings)