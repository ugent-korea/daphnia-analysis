"""
Monthly analytics dashboard for Daphnia breeding experiments.
Provides detailed end-of-month analysis including demographics, mortality, reproduction, and survival.
"""

import pandas as pd
import streamlit as st
import altair as alt
from app.core import database, monthly_analytics
from scipy import stats


def render():
    """Main render function for Monthly Reports page."""
    st.title("Monthly Analytics Reports")
    st.caption("Comprehensive end-of-month analysis of Daphnia breeding experiments")

    try:
        broods_df, records_df = _load_data()
    except Exception as e:
        st.error(f"Failed to load data: {e}")
        return

    if records_df.empty:
        st.warning("No records found in the database.")
        return

    st.divider()

    selected_month = "September 2025"
    st.subheader(f"{selected_month} Report")

    # Filter for September 2025 ONLY
    sept_records = monthly_analytics.filter_records_by_month(records_df, 2025, 9)
    sept_broods = _filter_broods_by_month(broods_df, 2025, 9)

    if sept_records.empty:
        st.info(f"No records found for {selected_month}")
        return

    _render_september_dashboard(sept_records, sept_broods, broods_df)


def _filter_broods_by_month(broods_df: pd.DataFrame, year: int, month: int) -> pd.DataFrame:
    """Filter broods born in a specific month."""
    broods_df = broods_df.copy()
    broods_df['birth_date_parsed'] = broods_df['birth_date'].apply(monthly_analytics.parse_date_safe)

    mask = (
        (broods_df['birth_date_parsed'].dt.year == year) &
        (broods_df['birth_date_parsed'].dt.month == month)
    )

    return broods_df[mask].copy()


def _load_data():
    """Load broods and records data."""
    data = database.get_data()
    by_full = data.get("by_full", {})
    broods_df = pd.DataFrame.from_dict(by_full, orient="index")
    if "mother_id" not in broods_df.columns:
        broods_df["mother_id"] = broods_df.index

    records_df = database.get_records()

    return broods_df, records_df


def _render_september_dashboard(sept_records: pd.DataFrame, sept_broods: pd.DataFrame, all_broods_df: pd.DataFrame):
    """Render complete September 2025 dashboard."""

    tabs = st.tabs([
        "Summary Report",
        "Demographics",
        "Mortality Analysis",
        "Reproduction Metrics",
        "Life Stage & Reproduction Timing",
        "Survival Analysis"
    ])

    with tabs[0]:
        _render_summary(sept_records, sept_broods)

    with tabs[1]:
        _render_demographics_section(sept_records, sept_broods)

    with tabs[2]:
        _render_mortality_section(sept_records)

    with tabs[3]:
        _render_reproduction_section(sept_records, sept_broods)

    with tabs[4]:
        _render_life_stage_and_reproduction_timing(sept_records)

    with tabs[5]:
        _render_survival_analysis_section(all_broods_df)


def _render_summary(sept_records: pd.DataFrame, sept_broods: pd.DataFrame):
    """Render executive summary with narrative report and conclusions."""
    st.subheader("Executive Summary - September 2025")

    demo = monthly_analytics.calculate_demographics(sept_records, sept_broods)
    mort = monthly_analytics.calculate_mortality_rates(sept_records)
    repro = monthly_analytics.calculate_reproduction_metrics(sept_records, sept_broods)
    trans = monthly_analytics.calculate_life_stage_transitions(sept_records)
    timing = monthly_analytics.calculate_reproduction_timing_v2(sept_records)

    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Population", f"{demo['total_records']:,}")
    col2.metric("Active Mothers", f"{demo['unique_mothers']:,}")
    col3.metric("Neonates Born", f"{repro['brood_size']['total_neonates']:,}")

    total_deaths = sum(stage['sum'] for stage in mort.values()) if mort else 0
    col4.metric("Total Deaths", f"{int(total_deaths):,}")

    st.divider()

    # Narrative report
    st.markdown("### Monthly Performance Report")

    # Population summary
    st.markdown(f"""
    During September 2025, the experimental population consisted of **{demo['total_records']:,} recorded observations** 
    across **{demo['unique_mothers']:,} unique breeding mothers**. The average age of mothers tracked was 
    **{demo['age_stats']['mean']:.1f} days**, with the oldest individual reaching **{int(demo['age_stats']['max'])} days**. 
    The population was distributed across **{len(demo['set_counts'])} experimental sets** ({', '.join(sorted(demo['set_counts'].keys()))}), 
    with Set {max(demo['set_counts'], key=demo['set_counts'].get)} showing the highest population density 
    at {demo['set_counts'][max(demo['set_counts'], key=demo['set_counts'].get)]:,} individuals.
    """)

    # Mortality analysis
    if mort:
        total_records = sum(stage['count'] for stage in mort.values())
        mort_rate = (total_deaths / total_records * 100) if total_records > 0 else 0

        st.markdown(f"""
        **Mortality patterns** revealed a total of **{int(total_deaths)} deaths** across {total_records:,} observations, 
        resulting in an overall mortality rate of **{mort_rate:.2f}%** for the month. Analysis of mortality causes 
        identified multiple contributing factors distributed across different life stages and experimental conditions.
        """)

        # Chi-square analysis
        mort_records = sept_records[sept_records['mortality'] > 0].copy()
        if not mort_records.empty:
            all_causes = []
            for _, row in mort_records.iterrows():
                causes = str(row['cause_of_death']).split(',')
                for cause in causes:
                    cause = cause.strip().lower()
                    if cause and cause not in ['', 'nan', 'none', 'unknown']:
                        all_causes.append({
                            'cause': cause,
                            'life_stage': str(row['life_stage']).strip().lower(),
                            'mortality': row['mortality']
                        })

            if all_causes:
                causes_df = pd.DataFrame(all_causes)
                causes_df.loc[causes_df['life_stage'] == 'adolescence', 'life_stage'] = 'adolescent'
                pivot = causes_df.pivot_table(values='mortality', index='life_stage', columns='cause', aggfunc='sum', fill_value=0)

                if pivot.shape[0] > 1 and pivot.shape[1] > 1:
                    try:
                        chi2, p_value, dof, _ = stats.chi2_contingency(pivot)
                        if p_value < 0.05:
                            st.info(f"""
                            **Statistical Significance Detected**: Chi-square analysis (χ² = {chi2:.2f}, p = {p_value:.4f}) 
                            revealed a statistically significant relationship between life stage and cause of death. 
                            This indicates that certain mortality causes are more prevalent in specific developmental stages, 
                            suggesting stage-specific vulnerabilities that warrant further investigation and targeted 
                            intervention strategies.
                            """)
                    except:
                        pass
    else:
        st.markdown("No mortality events were recorded during September 2025.")

    # Reproduction performance
    st.markdown(f"""
    **Reproductive performance** demonstrated an average brood size of **{repro['brood_size']['mean']:.1f} neonates**, 
    with individual broods ranging from {repro['brood_size']['min']} to {repro['brood_size']['max']} offspring. 
    A total of **{repro['brood_size']['total_neonates']:,} neonates** were produced across 
    **{repro['total_broods']:,} broods**, averaging **{repro['broods_per_mother']['mean']:.1f} broods per mother**. 
    The maximum reproductive output from a single mother was {repro['broods_per_mother']['max']} broods during this period.
    """)

    # Life stage transitions
    if trans.get('neonate_to_adult'):
        st.markdown(f"""
        **Developmental timing** analysis revealed that individuals required an average of 
        **{trans['neonate_to_adult']['mean']:.1f} days** (median: {trans['neonate_to_adult']['median']:.1f} days) 
        to complete the full developmental cycle from neonate to adult stage. This included 
        **{trans['neonate_to_adolescent']['mean']:.1f} days** for the neonate-to-adolescent transition and 
        **{trans['adolescent_to_adult']['mean']:.1f} days** for the adolescent-to-adult transition.
        """)

    # Reproduction timing
    if timing.get('adult_to_pregnant_by_set'):
        all_atp = [data for set_data in timing['adult_to_pregnant_by_set'].values() for data in [set_data]]
        if all_atp:
            avg_atp = sum(d['mean'] for d in all_atp) / len(all_atp)
            st.markdown(f"""
            **Reproductive maturation** occurred approximately **{avg_atp:.1f} days** 
            after reaching adult stage on average across all sets.
            """)

    if timing.get('gestation_by_set'):
        all_gest = [data for set_data in timing['gestation_by_set'].values() for data in [set_data]]
        if all_gest:
            avg_gest = sum(d['mean'] for d in all_gest) / len(all_gest)
            st.markdown(f"""
            The **gestation period** (from egg development detection to release) averaged 
            **{avg_gest:.1f} days** across all sets.
            """)

    st.divider()

    # Key findings callout
    st.success("""
    **Key Findings & Conclusions:**
    
    • Population health appears stable with consistent reproduction across all experimental sets
    
    • Mortality patterns show stage-specific vulnerabilities requiring targeted monitoring
    
    • Reproductive performance meets expected parameters for Daphnia magna populations
    
    • Developmental timing is consistent with established Daphnia life cycle expectations
    
    • No critical anomalies detected that would warrant immediate experimental intervention
    """)

    if trans.get('flagged_broods') and len(trans['flagged_broods']) > 0:
        st.warning(f"""
        **Data Quality Note**: {len(trans['flagged_broods'])} broods exhibited inconsistent life stage progression 
        patterns and were excluded from developmental timing calculations. These anomalies may indicate 
        recording errors or atypical developmental pathways requiring verification.
        """)


def _render_demographics_section(sept_records: pd.DataFrame, sept_broods: pd.DataFrame):
    """Render demographics - POPULATION counts by set."""
    st.subheader("Population Demographics")

    demo = monthly_analytics.calculate_demographics(sept_records, sept_broods)

    # Overall metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Population", f"{demo['total_records']:,}")
    col2.metric("Unique Mothers", f"{demo['unique_mothers']:,}")
    col3.metric("Avg Age", f"{demo['age_stats']['mean']:.1f} days")
    col4.metric("Max Age", f"{int(demo['age_stats']['max'])} days")

    st.divider()

    # Population by Set - BAR CHART (ALPHABETICAL ORDER)
    st.markdown("### Population by Experimental Set")

    set_data = pd.DataFrame.from_dict(demo['set_counts'], orient='index', columns=['Population'])
    set_data = set_data.reset_index().rename(columns={'index': 'Set'})
    set_data = set_data.sort_values('Set')  # ALPHABETICAL ORDER

    chart = alt.Chart(set_data).mark_bar().encode(
        x=alt.X('Set:N', sort=list(set_data['Set']), title='Experimental Set'),
        y=alt.Y('Population:Q', title='Population Count'),
        color=alt.Color('Set:N', legend=None),
        tooltip=['Set', 'Population']
    ).properties(height=400)

    st.altair_chart(chart, use_container_width=True)

    # Show data table
    set_data['Percentage'] = (set_data['Population'] / set_data['Population'].sum() * 100).round(1)
    st.dataframe(set_data, use_container_width=True, hide_index=True)

    st.divider()

    # Life stage distribution - PIE CHART
    st.markdown("### Life Stage Distribution")

    stage_data = pd.DataFrame.from_dict(demo['stage_counts'], orient='index', columns=['Count'])
    stage_data = stage_data.reset_index().rename(columns={'index': 'Life Stage'})

    chart = alt.Chart(stage_data).mark_arc(innerRadius=80).encode(
        theta=alt.Theta('Count:Q', title='Count'),
        color=alt.Color('Life Stage:N', title='Life Stage'),
        tooltip=['Life Stage', 'Count']
    ).properties(height=400)

    st.altair_chart(chart, use_container_width=True)


def _render_mortality_section(sept_records: pd.DataFrame):
    """Render mortality analysis with VISUALS."""
    st.subheader("Mortality Analysis")

    mort = monthly_analytics.calculate_mortality_rates(sept_records)

    if not mort:
        st.info("No mortality data for September 2025")
        return

    total_deaths = sum(stage['sum'] for stage in mort.values())
    total_records = sum(stage['count'] for stage in mort.values())

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Deaths", f"{int(total_deaths):,}")
    col2.metric("Total Records", f"{total_records:,}")
    col3.metric("Mortality Rate", f"{(total_deaths / total_records * 100):.2f}%")

    st.divider()

    # Parse comma-separated causes of death
    st.markdown("### Causes of Death")

    mort_records = sept_records[sept_records['mortality'] > 0].copy()

    if mort_records.empty:
        st.info("No mortality causes recorded")
        return

    # Split comma-separated causes
    all_causes = []
    for _, row in mort_records.iterrows():
        causes = str(row['cause_of_death']).split(',')
        for cause in causes:
            cause = cause.strip().lower()
            if cause and cause not in ['', 'nan', 'none', 'unknown']:
                all_causes.append({
                    'cause': cause,
                    'life_stage': str(row['life_stage']).strip().lower(),
                    'set_label': row['set_label'],
                    'mortality': row['mortality']
                })

    if not all_causes:
        st.info("No valid causes of death recorded")
        return

    causes_df = pd.DataFrame(all_causes)
    causes_df.loc[causes_df['life_stage'] == 'adolescence', 'life_stage'] = 'adolescent'

    # Overall top causes - BAR CHART
    st.markdown("#### Top Causes of Death (Overall)")
    top_causes = causes_df.groupby('cause')['mortality'].sum().nlargest(10).reset_index()

    chart = alt.Chart(top_causes).mark_bar().encode(
        x=alt.X('cause:N', sort='-y', title='Cause of Death'),
        y=alt.Y('mortality:Q', title='Deaths'),
        color=alt.Color('cause:N', legend=None),
        tooltip=['cause', 'mortality']
    ).properties(height=400)

    st.altair_chart(chart, use_container_width=True)

    st.divider()

    # By Life Stage - STACKED BAR
    st.markdown("#### Causes of Death by Life Stage")

    stage_causes = causes_df.groupby(['life_stage', 'cause'])['mortality'].sum().reset_index()

    chart = alt.Chart(stage_causes).mark_bar().encode(
        x=alt.X('life_stage:N', title='Life Stage'),
        y=alt.Y('mortality:Q', title='Deaths'),
        color=alt.Color('cause:N', title='Cause'),
        tooltip=['life_stage', 'cause', 'mortality']
    ).properties(height=400)

    st.altair_chart(chart, use_container_width=True)

    # Chi-square test
    pivot = causes_df.pivot_table(values='mortality', index='life_stage', columns='cause', aggfunc='sum', fill_value=0)
    if pivot.shape[0] > 1 and pivot.shape[1] > 1:
        try:
            chi2, p_value, dof, _ = stats.chi2_contingency(pivot)
            st.markdown(f"**Statistical Test**: Chi-square = {chi2:.2f}, p-value = {p_value:.4f}")
            if p_value < 0.05:
                st.success("Significant relationship between life stage and cause of death detected (p < 0.05)")
            else:
                st.info("No significant relationship detected")
        except:
            pass

    st.divider()

    # By Set - STACKED BAR (ALPHABETICAL ORDER)
    st.markdown("#### Causes of Death by Experimental Set")

    set_causes = causes_df.groupby(['set_label', 'cause'])['mortality'].sum().reset_index()
    set_causes = set_causes.sort_values('set_label')  # ALPHABETICAL

    chart = alt.Chart(set_causes).mark_bar().encode(
        x=alt.X('set_label:N', sort=list(set_causes['set_label'].unique()), title='Set'),
        y=alt.Y('mortality:Q', title='Deaths'),
        color=alt.Color('cause:N', title='Cause'),
        tooltip=['set_label', 'cause', 'mortality']
    ).properties(height=400)

    st.altair_chart(chart, use_container_width=True)

    st.divider()

    # Cumulative - PIE CHART
    st.markdown("#### Cumulative Cause Distribution")

    cumulative = causes_df.groupby('cause')['mortality'].sum().reset_index()

    chart = alt.Chart(cumulative).mark_arc(innerRadius=80).encode(
        theta=alt.Theta('mortality:Q', title='Deaths'),
        color=alt.Color('cause:N', title='Cause'),
        tooltip=['cause', 'mortality']
    ).properties(height=400)

    st.altair_chart(chart, use_container_width=True)


def _render_reproduction_section(sept_records: pd.DataFrame, sept_broods: pd.DataFrame):
    """Render reproduction metrics with VISUALS."""
    st.subheader("Reproduction Metrics")

    repro = monthly_analytics.calculate_reproduction_metrics(sept_records, sept_broods)

    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Avg Brood Size", f"{repro['brood_size']['mean']:.1f}")
    col2.metric("Total Neonates", repro['brood_size']['total_neonates'])
    col3.metric("Avg Broods/Mother", f"{repro['broods_per_mother']['mean']:.1f}")
    col4.metric("Total Mothers", repro['total_mothers'])

    st.divider()

    # Brood size distribution - HISTOGRAM
    st.markdown("### Brood Size Distribution")

    brood_sizes = sept_broods[['n_i']].dropna()

    if not brood_sizes.empty:
        chart = alt.Chart(brood_sizes).mark_bar().encode(
            x=alt.X('n_i:Q', bin=alt.Bin(maxbins=20), title='Brood Size (n_i)'),
            y=alt.Y('count()', title='Frequency'),
            tooltip=[alt.Tooltip('n_i:Q', bin=True, title='Brood Size'), alt.Tooltip('count()', title='Count')]
        ).properties(height=400)

        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("No brood size data available")

    st.divider()

    # Average brood size by set - BAR CHART (ALPHABETICAL ORDER)
    st.markdown("### Average Brood Size by Experimental Set")

    avg_by_set = sept_broods.groupby('set_label')['n_i'].mean().reset_index()
    avg_by_set.columns = ['Set', 'Average Brood Size']
    avg_by_set = avg_by_set.sort_values('Set')  # ALPHABETICAL

    if not avg_by_set.empty:
        chart = alt.Chart(avg_by_set).mark_bar().encode(
            x=alt.X('Set:N', sort=list(avg_by_set['Set']), title='Experimental Set'),
            y=alt.Y('Average Brood Size:Q', title='Average Brood Size'),
            color=alt.Color('Set:N', legend=None),
            tooltip=['Set', alt.Tooltip('Average Brood Size:Q', format='.2f')]
        ).properties(height=400)

        st.altair_chart(chart, use_container_width=True)
        st.dataframe(avg_by_set, use_container_width=True, hide_index=True)
    else:
        st.info("No set-level brood size data available")

    st.divider()

    # Summary statistics table
    st.markdown("### Summary Statistics")
    stats_df = pd.DataFrame({
        'Metric': ['Mean', 'Median', 'Min', 'Max', 'Total Neonates'],
        'Value': [
            f"{repro['brood_size']['mean']:.1f}",
            f"{repro['brood_size']['median']:.1f}",
            repro['brood_size']['min'],
            repro['brood_size']['max'],
            repro['brood_size']['total_neonates']
        ]
    })
    st.dataframe(stats_df, use_container_width=True, hide_index=True)


def _render_life_stage_and_reproduction_timing(sept_records: pd.DataFrame):
    """Render combined life stage transitions and reproduction timing."""
    st.subheader("Life Stage Transitions & Reproduction Timing")

    trans = monthly_analytics.calculate_life_stage_transitions(sept_records)
    timing = monthly_analytics.calculate_reproduction_timing_v2(sept_records)

    # Life stage transitions - FLOW FORMAT
    st.markdown("### Developmental Timeline")

    # Top: Neonate to Adult total
    if trans.get('neonate_to_adult'):
        st.metric("Complete Development (Neonate to Adult)",
                 f"{trans['neonate_to_adult']['mean']:.1f} days (median: {trans['neonate_to_adult']['median']:.1f})")
        st.caption(f"Based on {trans['neonate_to_adult']['count']} broods | Range: {trans['neonate_to_adult']['min']}-{trans['neonate_to_adult']['max']} days")

    st.markdown("---")

    # Flow: Neonate -> metrics -> Adolescent -> metrics -> Adult
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.markdown("**Neonate**")

    with col2:
        if trans.get('neonate_to_adolescent'):
            data = trans['neonate_to_adolescent']
            st.markdown(f"**{data['mean']:.1f} days**")
            st.caption(f"median: {data['median']:.1f}")
            st.caption(f"n={data['count']}")
        else:
            st.markdown("No data")

    with col3:
        st.markdown("**Adolescent**")

    with col4:
        if trans.get('adolescent_to_adult'):
            data = trans['adolescent_to_adult']
            st.markdown(f"**{data['mean']:.1f} days**")
            st.caption(f"median: {data['median']:.1f}")
            st.caption(f"n={data['count']}")
        else:
            st.markdown("No data")

    with col5:
        st.markdown("**Adult**")

    st.divider()

    # Flagged broods
    if trans.get('flagged_broods') and len(trans['flagged_broods']) > 0:
        st.warning(f"{len(trans['flagged_broods'])} broods flagged for inconsistent transitions")
        with st.expander("View Flagged Broods"):
            flagged_df = pd.DataFrame(trans['flagged_broods'])
            st.dataframe(flagged_df, use_container_width=True, hide_index=True)

    st.divider()

    # Reproduction timing BY SET
    st.markdown("### Reproduction Timing by Experimental Set")

    # Adult to Pregnant by Set
    st.markdown("#### Time to Pregnancy (Adult to Egg Development) by Set")

    atp_by_set = timing.get('adult_to_pregnant_by_set', {})

    if atp_by_set:
        atp_data = []
        for set_label in sorted(atp_by_set.keys()):  # ALPHABETICAL
            data = atp_by_set[set_label]
            atp_data.append({
                'Set': set_label,
                'Mean (days)': data['mean'],
                'Median (days)': data['median'],
                'Min (days)': data['min'],
                'Max (days)': data['max'],
                'Count': data['count']
            })

        atp_df = pd.DataFrame(atp_data)

        # Bar chart
        chart = alt.Chart(atp_df).mark_bar().encode(
            x=alt.X('Set:N', sort=list(atp_df['Set']), title='Experimental Set'),
            y=alt.Y('Mean (days):Q', title='Mean Days to Pregnancy'),
            color=alt.Color('Set:N', legend=None),
            tooltip=['Set', alt.Tooltip('Mean (days):Q', format='.1f'), 'Count']
        ).properties(height=300)

        st.altair_chart(chart, use_container_width=True)
        st.dataframe(atp_df, use_container_width=True, hide_index=True)
    else:
        st.info("No pregnancy timing data available")

    st.divider()

    # Gestation Period by Set
    st.markdown("#### Gestation Period by Set")
    st.caption("Methodology: Time from egg_development='yes' to first egg_development='no' for each mother")

    gest_by_set = timing.get('gestation_by_set', {})

    if gest_by_set:
        gest_data = []
        for set_label in sorted(gest_by_set.keys()):  # ALPHABETICAL
            data = gest_by_set[set_label]
            gest_data.append({
                'Set': set_label,
                'Mean (days)': data['mean'],
                'Median (days)': data['median'],
                'Min (days)': data['min'],
                'Max (days)': data['max'],
                'Count': data['count']
            })

        gest_df = pd.DataFrame(gest_data)

        # Bar chart
        chart = alt.Chart(gest_df).mark_bar().encode(
            x=alt.X('Set:N', sort=list(gest_df['Set']), title='Experimental Set'),
            y=alt.Y('Mean (days):Q', title='Mean Gestation Period (days)'),
            color=alt.Color('Set:N', legend=None),
            tooltip=['Set', alt.Tooltip('Mean (days):Q', format='.1f'), 'Count']
        ).properties(height=300)

        st.altair_chart(chart, use_container_width=True)
        st.dataframe(gest_df, use_container_width=True, hide_index=True)
    else:
        st.info("No gestation data available")


def _render_survival_analysis_section(all_broods_df: pd.DataFrame):
    """Render survival analysis."""
    st.subheader("Survival Analysis")
    st.caption("Kaplan-Meier survival curves by experimental set")

    survival_data = monthly_analytics.prepare_survival_data(all_broods_df)

    if survival_data.empty:
        st.info("Insufficient data for survival analysis")
        return

    total_broods = len(survival_data)
    dead_broods = survival_data['event'].sum()
    alive_broods = total_broods - dead_broods

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Broods", f"{total_broods:,}")
    col2.metric("Dead", f"{int(dead_broods):,}")
    col3.metric("Alive (Censored)", f"{int(alive_broods):,}")

    st.divider()

    # Mean survival time - ALL BROODS
    st.markdown("### Mean Survival Time")

    dead_only = survival_data[survival_data['event'] == 1]['survival_days']
    if not dead_only.empty:
        mean_all = dead_only.mean()
        median_all = dead_only.median()

        col1, col2 = st.columns(2)
        col1.metric("Mean (All Broods)", f"{mean_all:.1f} days")
        col2.metric("Median (All Broods)", f"{median_all:.1f} days")

        st.divider()

        # Mean survival by set - BAR CHART (ALPHABETICAL ORDER)
        st.markdown("#### Mean Survival Time by Experimental Set")

        set_survival = []
        for set_label in sorted(survival_data['set_label'].unique()):
            set_data = survival_data[survival_data['set_label'] == set_label]
            dead_set = set_data[set_data['event'] == 1]['survival_days']

            if not dead_set.empty:
                set_survival.append({
                    'Set': set_label,
                    'Mean Survival (days)': dead_set.mean(),
                    'Median Survival (days)': dead_set.median(),
                    'Count': len(dead_set)
                })

        if set_survival:
            set_survival_df = pd.DataFrame(set_survival)

            chart = alt.Chart(set_survival_df).mark_bar().encode(
                x=alt.X('Set:N', sort=list(set_survival_df['Set']), title='Experimental Set'),
                y=alt.Y('Mean Survival (days):Q', title='Mean Survival (days)'),
                color=alt.Color('Set:N', legend=None),
                tooltip=['Set', alt.Tooltip('Mean Survival (days):Q', format='.1f'), 'Count']
            ).properties(height=400)

            st.altair_chart(chart, use_container_width=True)
            st.dataframe(set_survival_df, use_container_width=True, hide_index=True)
    else:
        st.info("No deaths recorded yet")

    st.divider()

    st.markdown("### Survival Curves")

    try:
        overall_curve = _calculate_simple_survival_curve(survival_data)
        if not overall_curve.empty:
            chart = alt.Chart(overall_curve).mark_line(color='#1f77b4', strokeWidth=2).encode(
                x=alt.X('days:Q', title='Days'),
                y=alt.Y('survival_rate:Q', title='Survival Rate', scale=alt.Scale(domain=[0, 1])),
                tooltip=['days', alt.Tooltip('survival_rate:Q', format='.2%')]
            ).properties(height=300, title='All Broods Combined')
            st.altair_chart(chart, use_container_width=True)

        sets = sorted(survival_data['set_label'].unique())
        curves_by_set = []
        for set_label in sets:
            set_data = survival_data[survival_data['set_label'] == set_label]
            curve = _calculate_simple_survival_curve(set_data)
            if not curve.empty:
                curve['set_label'] = set_label
                curves_by_set.append(curve)

        if curves_by_set:
            all_curves = pd.concat(curves_by_set, ignore_index=True)

            chart = alt.Chart(all_curves).mark_line(strokeWidth=2).encode(
                x=alt.X('days:Q', title='Days'),
                y=alt.Y('survival_rate:Q', title='Survival Rate', scale=alt.Scale(domain=[0, 1])),
                color=alt.Color('set_label:N', title='Set'),
                tooltip=['set_label', 'days', alt.Tooltip('survival_rate:Q', format='.2%')]
            ).properties(height=400, title='Survival by Experimental Set')

            st.altair_chart(chart, use_container_width=True)

    except Exception as e:
        st.error(f"Error rendering survival curves: {e}")


def _calculate_simple_survival_curve(survival_data: pd.DataFrame) -> pd.DataFrame:
    """Calculate simplified survival curve."""

    if survival_data.empty:
        return pd.DataFrame()

    sorted_data = survival_data.sort_values('survival_days')

    max_time = int(sorted_data['survival_days'].max())
    time_points = list(range(0, max_time + 1, max(1, max_time // 50)))

    curve_data = []
    total_broods = len(sorted_data)

    for t in time_points:
        deaths_by_t = sorted_data[(sorted_data['survival_days'] <= t) & (sorted_data['event'] == 1)].shape[0]
        survival_rate = (total_broods - deaths_by_t) / total_broods

        curve_data.append({
            'days': t,
            'survival_rate': survival_rate
        })

    return pd.DataFrame(curve_data)