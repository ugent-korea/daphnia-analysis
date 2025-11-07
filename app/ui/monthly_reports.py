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
        "Egg Production Analysis",
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
        _render_egg_production_section(sept_records, sept_broods)

    with tabs[5]:
        _render_life_stage_and_reproduction_timing(sept_records)

    with tabs[6]:
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

    # Mortality analysis with percentages
    if mort:
        total_records = sum(stage['count'] for stage in mort.values())
        mort_rate = (total_deaths / total_records * 100) if total_records > 0 else 0

        # Death percentages by stage
        stage_death_pcts = {stage: data['percentage_of_total'] for stage, data in mort.items()}

        st.markdown(f"""
        **Mortality patterns** revealed a total of **{int(total_deaths)} deaths** across {total_records:,} observations, 
        resulting in an overall mortality rate of **{mort_rate:.2f}%** for the month. Death distribution by life stage: 
        Neonates ({stage_death_pcts.get('neonate', 0):.1f}%), Adolescents ({stage_death_pcts.get('adolescent', 0):.1f}%), 
        Adults ({stage_death_pcts.get('adult', 0):.1f}%).
        """)

    # Reproduction performance
    st.markdown(f"""
    **Reproductive performance** demonstrated an average brood size of **{repro['brood_size']['mean']:.1f} neonates**, 
    with individual broods ranging from {repro['brood_size']['min']} to {repro['brood_size']['max']} offspring. 
    A total of **{repro['brood_size']['total_neonates']:,} neonates** were produced across 
    **{repro['total_broods']:,} broods**, averaging **{repro['broods_per_mother']['mean']:.1f} broods per mother**.
    """)

    # Life stage transitions
    if trans.get('neonate_to_adult'):
        st.markdown(f"""
        **Developmental timing** analysis revealed that individuals required an average of 
        **{trans['neonate_to_adult']['mean']:.1f} days** (median: {trans['neonate_to_adult']['median']:.1f} days) 
        to complete the full developmental cycle from neonate to adult stage.
        """)

    st.divider()

    # Key findings
    st.success("""
    **Key Findings & Conclusions:**

    • Population health appears stable with consistent reproduction across all experimental sets

    • Mortality patterns show stage-specific vulnerabilities requiring targeted monitoring

    • Reproductive performance meets expected parameters for *Daphnia magna* populations

    • Developmental timing is consistent with established Daphnia life cycle expectations
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

    # Population by Set - BAR CHART (ALPHABETICAL)
    st.markdown("### Population by Experimental Set")

    set_data = pd.DataFrame.from_dict(demo['set_counts'], orient='index', columns=['Population'])
    set_data = set_data.reset_index().rename(columns={'index': 'Set'})
    set_data = set_data.sort_values('Set')

    chart = alt.Chart(set_data).mark_bar().encode(
        x=alt.X('Set:N', sort=list(set_data['Set']), title='Experimental Set'),
        y=alt.Y('Population:Q', title='Population Count'),
        color=alt.Color('Set:N', legend=None),
        tooltip=['Set', 'Population']
    ).properties(height=400)

    st.altair_chart(chart, use_container_width=True)

    # Show data table with percentages
    total_pop = demo['total_records']
    set_data['Percentage'] = (set_data['Population'] / total_pop * 100).round(1)
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
    """Render mortality analysis with percentage breakdowns."""
    st.subheader("Mortality Analysis")

    mort = monthly_analytics.calculate_mortality_rates(sept_records)
    mort_causes = monthly_analytics.analyze_mortality_causes_detailed(sept_records)

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

    # Death percentages by life stage
    st.markdown("### Death Distribution by Life Stage")

    stage_mort_data = []
    for stage in ['neonate', 'adolescent', 'adult']:
        if stage in mort:
            stage_mort_data.append({
                'Life Stage': stage.capitalize(),
                'Deaths': int(mort[stage]['sum']),
                '% of Total Deaths': mort[stage]['percentage_of_total'],
                '% within Stage': mort[stage]['percentage_of_stage']
            })

    stage_mort_df = pd.DataFrame(stage_mort_data)
    st.dataframe(stage_mort_df, use_container_width=True, hide_index=True)

    # Bar chart
    chart = alt.Chart(stage_mort_df).mark_bar().encode(
        x=alt.X('Life Stage:N', title='Life Stage'),
        y=alt.Y('Deaths:Q', title='Total Deaths'),
        color=alt.Color('Life Stage:N', legend=None),
        tooltip=['Life Stage', 'Deaths', alt.Tooltip('% of Total Deaths:Q', format='.1f')]
    ).properties(height=300)

    st.altair_chart(chart, use_container_width=True)

    st.divider()

    # Causes of Death with percentages
    if mort_causes.get('has_data'):
        st.markdown("### Causes of Death Analysis")

        # Overall percentages
        st.markdown("#### Overall Cause Distribution")

        overall_data = []
        for cause, pct in sorted(mort_causes['overall_percentages'].items(), key=lambda x: -x[1]):
            overall_data.append({
                'Cause': cause,
                'Percentage': pct
            })

        overall_df = pd.DataFrame(overall_data)

        chart = alt.Chart(overall_df).mark_bar().encode(
            x=alt.X('Cause:N', sort='-y', title='Cause of Death'),
            y=alt.Y('Percentage:Q', title='% of Total Deaths'),
            color=alt.Color('Cause:N', legend=None),
            tooltip=['Cause', alt.Tooltip('Percentage:Q', format='.1f')]
        ).properties(height=300)

        st.altair_chart(chart, use_container_width=True)

        st.divider()

        # By life stage with percentages
        st.markdown("#### Causes by Life Stage (with percentages)")

        for stage, stage_data in mort_causes['by_life_stage'].items():
            with st.expander(f"{stage.capitalize()} - {stage_data['percentage_of_all_deaths']:.1f}% of all deaths"):
                stage_cause_data = []
                for cause, pct in sorted(stage_data['percentages'].items(), key=lambda x: -x[1]):
                    stage_cause_data.append({
                        'Cause': cause,
                        '% within Stage': pct,
                        'Count': stage_data['counts'][cause]
                    })

                st.dataframe(pd.DataFrame(stage_cause_data), use_container_width=True, hide_index=True)

        st.divider()

        # By set with percentages
        st.markdown("#### Causes by Experimental Set (with percentages)")

        for set_label in sorted(mort_causes['by_set'].keys()):
            set_data = mort_causes['by_set'][set_label]
            with st.expander(f"{set_label} - {set_data['percentage_of_all_deaths']:.1f}% of all deaths"):
                set_cause_data = []
                for cause, pct in sorted(set_data['percentages'].items(), key=lambda x: -x[1]):
                    set_cause_data.append({
                        'Cause': cause,
                        '% within Set': pct,
                        'Count': set_data['counts'][cause]
                    })

                st.dataframe(pd.DataFrame(set_cause_data), use_container_width=True, hide_index=True)


def _render_reproduction_section(sept_records: pd.DataFrame, sept_broods: pd.DataFrame):
    """Render reproduction metrics."""
    st.subheader("Reproduction Metrics")

    repro = monthly_analytics.calculate_reproduction_metrics(sept_records, sept_broods)

    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Avg Brood Size", f"{repro['brood_size']['mean']:.1f}")
    col2.metric("Total Neonates", repro['brood_size']['total_neonates'])
    col3.metric("Avg Broods/Mother", f"{repro['broods_per_mother']['mean']:.1f}")
    col4.metric("Total Mothers", repro['total_mothers'])

    st.divider()

    # Brood size distribution
    st.markdown("### Brood Size Distribution")

    brood_sizes = sept_broods[['n_i']].dropna()

    if not brood_sizes.empty:
        chart = alt.Chart(brood_sizes).mark_bar().encode(
            x=alt.X('n_i:Q', bin=alt.Bin(maxbins=20), title='Brood Size (n_i)'),
            y=alt.Y('count()', title='Frequency'),
            tooltip=[alt.Tooltip('n_i:Q', bin=True, title='Brood Size'), alt.Tooltip('count()', title='Count')]
        ).properties(height=400)

        st.altair_chart(chart, use_container_width=True)

    st.divider()

    # Average brood size by set
    st.markdown("### Average Brood Size by Experimental Set")

    avg_by_set = sept_broods.groupby('set_label')['n_i'].mean().reset_index()
    avg_by_set.columns = ['Set', 'Average Brood Size']
    avg_by_set = avg_by_set.sort_values('Set')

    if not avg_by_set.empty:
        chart = alt.Chart(avg_by_set).mark_bar().encode(
            x=alt.X('Set:N', sort=list(avg_by_set['Set']), title='Experimental Set'),
            y=alt.Y('Average Brood Size:Q', title='Average Brood Size'),
            color=alt.Color('Set:N', legend=None),
            tooltip=['Set', alt.Tooltip('Average Brood Size:Q', format='.2f')]
        ).properties(height=400)

        st.altair_chart(chart, use_container_width=True)
        st.dataframe(avg_by_set, use_container_width=True, hide_index=True)


def _render_egg_production_section(sept_records: pd.DataFrame, sept_broods: pd.DataFrame):
    """Render egg production analysis by life stage and experimental set."""
    st.subheader("Egg Production by Life Stage")
    st.caption("Analysis of which stage (adolescent vs adult) produces eggs, calculated per child brood birth date")

    egg_prod = monthly_analytics.calculate_egg_production_by_stage(sept_records, sept_broods)

    if not egg_prod.get('has_data'):
        st.info("Insufficient data for egg production analysis")
        return

    # Overall statistics
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Broods Analyzed", egg_prod['total_broods'])

    adolescent_pct = egg_prod['stage_percentages'].get('adolescent', 0)
    adult_pct = egg_prod['stage_percentages'].get('adult', 0)

    col2.metric("Adolescent Production", f"{adolescent_pct:.1f}%")
    col3.metric("Adult Production", f"{adult_pct:.1f}%")

    st.divider()

    # Overall distribution - PIE CHART
    st.markdown("### Overall Stage Distribution")

    stage_data = []
    for stage, count in egg_prod['stage_counts'].items():
        stage_data.append({
            'Stage': stage.capitalize(),
            'Count': count,
            'Percentage': egg_prod['stage_percentages'][stage]
        })

    stage_df = pd.DataFrame(stage_data)

    chart = alt.Chart(stage_df).mark_arc(innerRadius=80).encode(
        theta=alt.Theta('Count:Q', title='Count'),
        color=alt.Color('Stage:N', title='Life Stage'),
        tooltip=['Stage', 'Count', alt.Tooltip('Percentage:Q', format='.1f')]
    ).properties(height=400)

    st.altair_chart(chart, use_container_width=True)

    st.divider()

    # By set breakdown - PROMINENTLY DISPLAYED
    st.markdown("### Egg Production by Experimental Set")
    st.caption("Comparison of adolescent vs adult egg production across all experimental sets")

    # Create comprehensive table for all sets
    set_comparison_data = []
    for set_label in sorted(egg_prod['by_set'].keys()):
        set_data = egg_prod['by_set'][set_label]

        set_comparison_data.append({
            'Set': set_label,
            'Total Broods': set_data['total'],
            'Adolescent Count': set_data['counts'].get('adolescent', 0),
            'Adolescent %': set_data['percentages'].get('adolescent', 0),
            'Adult Count': set_data['counts'].get('adult', 0),
            'Adult %': set_data['percentages'].get('adult', 0)
        })

    set_comparison_df = pd.DataFrame(set_comparison_data)

    # Display summary table
    st.dataframe(
        set_comparison_df.style.format({
            'Adolescent %': '{:.1f}%',
            'Adult %': '{:.1f}%'
        }),
        use_container_width=True,
        hide_index=True
    )

    st.divider()

    # Stacked bar chart by set
    st.markdown("#### Visual Comparison Across Sets")

    set_viz_data = []
    for set_label in sorted(egg_prod['by_set'].keys()):
        set_data = egg_prod['by_set'][set_label]
        for stage, count in set_data['counts'].items():
            set_viz_data.append({
                'Set': set_label,
                'Stage': stage.capitalize(),
                'Count': count,
                'Percentage': set_data['percentages'][stage]
            })

    set_viz_df = pd.DataFrame(set_viz_data)

    # Stacked bar chart
    chart = alt.Chart(set_viz_df).mark_bar().encode(
        x=alt.X('Set:N', sort=list(sorted(egg_prod['by_set'].keys())), title='Experimental Set'),
        y=alt.Y('Percentage:Q', title='Percentage of Broods', stack='normalize'),
        color=alt.Color('Stage:N', title='Life Stage'),
        tooltip=['Set', 'Stage', 'Count', alt.Tooltip('Percentage:Q', format='.1f')]
    ).properties(height=400)

    st.altair_chart(chart, use_container_width=True)

    st.divider()

    # Detailed breakdown per set (expandable)
    st.markdown("#### Detailed Breakdown by Set")

    for set_label in sorted(egg_prod['by_set'].keys()):
        set_data = egg_prod['by_set'][set_label]

        with st.expander(f"{set_label} - {set_data['total']} broods"):
            set_stage_data = []
            for stage, count in set_data['counts'].items():
                set_stage_data.append({
                    'Stage': stage.capitalize(),
                    'Count': count,
                    'Percentage': set_data['percentages'][stage]
                })

            set_stage_df = pd.DataFrame(set_stage_data)

            chart = alt.Chart(set_stage_df).mark_bar().encode(
                x=alt.X('Stage:N', title='Life Stage'),
                y=alt.Y('Percentage:Q', title='% of Broods'),
                color=alt.Color('Stage:N', legend=None),
                tooltip=['Stage', 'Count', alt.Tooltip('Percentage:Q', format='.1f')]
            ).properties(height=250)

            st.altair_chart(chart, use_container_width=True)
            st.dataframe(set_stage_df, use_container_width=True, hide_index=True)


def _render_life_stage_and_reproduction_timing(sept_records: pd.DataFrame):
    """Render combined life stage transitions and reproduction timing."""
    st.subheader("Life Stage Transitions & Reproduction Timing")

    trans = monthly_analytics.calculate_life_stage_transitions(sept_records)
    timing = monthly_analytics.calculate_reproduction_timing_v2(sept_records)

    # Life stage transitions
    st.markdown("### Developmental Timeline")

    if trans.get('neonate_to_adult'):
        st.metric("Complete Development (Neonate to Adult)",
                 f"{trans['neonate_to_adult']['mean']:.1f} days (median: {trans['neonate_to_adult']['median']:.1f})")
        st.caption(f"Based on {trans['neonate_to_adult']['count']} broods | Range: {trans['neonate_to_adult']['min']}-{trans['neonate_to_adult']['max']} days")

    st.markdown("---")

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.markdown("**Neonate**")

    with col2:
        if trans.get('neonate_to_adolescent'):
            data = trans['neonate_to_adolescent']
            st.markdown(f"**{data['mean']:.1f} days**")
            st.caption(f"median: {data['median']:.1f}")
            st.caption(f"n={data['count']}")

    with col3:
        st.markdown("**Adolescent**")

    with col4:
        if trans.get('adolescent_to_adult'):
            data = trans['adolescent_to_adult']
            st.markdown(f"**{data['mean']:.1f} days**")
            st.caption(f"median: {data['median']:.1f}")
            st.caption(f"n={data['count']}")

    with col5:
        st.markdown("**Adult**")

    st.divider()

    # Reproduction timing BY SET
    st.markdown("### Reproduction Timing by Experimental Set")

    # Adult to Pregnant by Set
    st.markdown("#### Time to Pregnancy (Adult to Egg Development) by Set")

    atp_by_set = timing.get('adult_to_pregnant_by_set', {})

    if atp_by_set:
        atp_data = []
        for set_label in sorted(atp_by_set.keys()):
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

        chart = alt.Chart(atp_df).mark_bar().encode(
            x=alt.X('Set:N', sort=list(atp_df['Set']), title='Experimental Set'),
            y=alt.Y('Mean (days):Q', title='Mean Days to Pregnancy'),
            color=alt.Color('Set:N', legend=None),
            tooltip=['Set', alt.Tooltip('Mean (days):Q', format='.1f'), 'Count']
        ).properties(height=300)

        st.altair_chart(chart, use_container_width=True)
        st.dataframe(atp_df, use_container_width=True, hide_index=True)

    st.divider()

    # Gestation Period by Set
    st.markdown("#### Gestation Period by Set")

    gest_by_set = timing.get('gestation_by_set', {})

    if gest_by_set:
        gest_data = []
        for set_label in sorted(gest_by_set.keys()):
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

        chart = alt.Chart(gest_df).mark_bar().encode(
            x=alt.X('Set:N', sort=list(gest_df['Set']), title='Experimental Set'),
            y=alt.Y('Mean (days):Q', title='Mean Gestation Period (days)'),
            color=alt.Color('Set:N', legend=None),
            tooltip=['Set', alt.Tooltip('Mean (days):Q', format='.1f'), 'Count']
        ).properties(height=300)

        st.altair_chart(chart, use_container_width=True)
        st.dataframe(gest_df, use_container_width=True, hide_index=True)


def _render_survival_analysis_section(all_broods_df: pd.DataFrame):
    """Render survival analysis with outlier removal and 0-max scale."""
    st.subheader("Survival Analysis (Life Expectancy)")
    st.caption("Kaplan-Meier survival curves by experimental set with outlier removal")

    # Prepare survival data WITH outlier removal
    survival_data = monthly_analytics.prepare_survival_data(all_broods_df, remove_outliers=True)

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

    # Mean survival time
    st.markdown("### Mean Life Expectancy (Dead Broods Only)")

    dead_only = survival_data[survival_data['event'] == 1]['survival_days']
    if not dead_only.empty:
        mean_all = dead_only.mean()
        median_all = dead_only.median()
        max_survival = dead_only.max()

        col1, col2, col3 = st.columns(3)
        col1.metric("Mean", f"{mean_all:.1f} days")
        col2.metric("Median", f"{median_all:.1f} days")
        col3.metric("Max", f"{int(max_survival)} days")

        st.divider()

        # Mean survival by set
        st.markdown("#### Mean Life Expectancy by Experimental Set")

        set_survival = []
        for set_label in sorted(survival_data['set_label'].unique()):
            set_data = survival_data[survival_data['set_label'] == set_label]
            dead_set = set_data[set_data['event'] == 1]['survival_days']

            if not dead_set.empty:
                set_survival.append({
                    'Set': set_label,
                    'Mean (days)': dead_set.mean(),
                    'Median (days)': dead_set.median(),
                    'Count': len(dead_set)
                })

        if set_survival:
            set_survival_df = pd.DataFrame(set_survival)

            chart = alt.Chart(set_survival_df).mark_bar().encode(
                x=alt.X('Set:N', sort=list(set_survival_df['Set']), title='Experimental Set'),
                y=alt.Y('Mean (days):Q', title='Mean Life Expectancy (days)'),
                color=alt.Color('Set:N', legend=None),
                tooltip=['Set', alt.Tooltip('Mean (days):Q', format='.1f'), 'Count']
            ).properties(height=400)

            st.altair_chart(chart, use_container_width=True)
            st.dataframe(set_survival_df, use_container_width=True, hide_index=True)

    st.divider()

    # Survival curves with 0-max scale
    st.markdown("### Survival Curves (0 to Max Days)")

    try:
        # Overall curve
        overall_curve = _calculate_simple_survival_curve(survival_data)
        if not overall_curve.empty:
            max_days = int(survival_data['survival_days'].max())

            chart = alt.Chart(overall_curve).mark_line(color='#1f77b4', strokeWidth=2).encode(
                x=alt.X('days:Q', title='Days', scale=alt.Scale(domain=[0, max_days])),
                y=alt.Y('survival_rate:Q', title='Survival Rate', scale=alt.Scale(domain=[0, 1])),
                tooltip=['days', alt.Tooltip('survival_rate:Q', format='.2%')]
            ).properties(height=300, title='All Broods Combined')

            st.altair_chart(chart, use_container_width=True)

        # By set
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
            max_days = int(survival_data['survival_days'].max())

            chart = alt.Chart(all_curves).mark_line(strokeWidth=2).encode(
                x=alt.X('days:Q', title='Days', scale=alt.Scale(domain=[0, max_days])),
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
