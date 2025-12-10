"""
Monthly Reports landing page - Information about the monthly reports feature
"""

import streamlit as st

def render():
    """Render the monthly reports information page."""
    st.title("📅 Monthly Reports - Information")

    st.markdown("""
    ### About Monthly Reports

    The Monthly Reports feature provides comprehensive end-of-month analysis of *Daphnia magna* breeding experiments.
    Each report is automatically filtered to show only data from the selected month.

    ### Available Reports

    Navigate to **📊 Monthly Reports** from the sidebar to access:
    - **September 2025** - Complete monthly analysis
    - **October 2025** - Complete monthly analysis  
    - **November 2025** - Complete monthly analysis

    Select the desired month from the dropdown to view its specific data.

    ### Report Sections

    Each monthly report includes:

    1. **Summary Report** - Executive summary with key metrics and narrative
    2. **Demographics** - Population distribution by set and life stage
    3. **Mortality Analysis** - Death rates by stage and causes
    4. **Reproduction Metrics** - Brood sizes and reproductive performance
    5. **Egg Production Analysis** - Stage-based egg production (adolescent vs adult)
    6. **Life Stage & Reproduction Timing** - Developmental timelines and gestation periods
    7. **Survival Analysis** - Kaplan-Meier curves and life expectancy

    ### Data Filtering

    All data in each monthly report is **strictly filtered** to show only:
    - Records from that specific month (by date)
    - Broods born in that specific month (by birth_date)

    This ensures accurate month-over-month comparisons.

    ### Manual Reporting

    Each monthly report includes text areas for you to write:
    - Executive summary in your own words
    - Key observations and context
    - Action items and follow-ups

    The automated analytics provide the numbers, but the narrative is yours to craft.

    ### Coming Soon

    Future enhancements planned:
    - **Cross-Month Comparisons**: Compare metrics across multiple months
    - **Trend Analysis**: Visualize population trends over time
    - **Statistical Testing**: Identify significant changes month-over-month
    - **Export Reports**: Download complete reports as PDF or Excel
    """)

    st.divider()

    st.info("👈 Navigate to **📊 Monthly Reports** in the sidebar to view detailed monthly analyses")
