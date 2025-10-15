"""
Visualization logic for Daphnia analysis charts.
Separates chart generation from UI rendering.
"""

import pandas as pd
import altair as alt
from typing import Optional, Tuple


# ===========================================================
# Data Cleaning Helpers
# ===========================================================

def _clean_and_split_values(series: pd.Series) -> pd.Series:
    """
    Clean a series by:
    1. Filtering out empty/null values
    2. Splitting comma-separated values
    3. Stripping whitespace
    
    Args:
        series: Pandas Series with potentially comma-separated values
        
    Returns:
        Cleaned and expanded Series
    """
    # Remove nulls and empty strings
    cleaned = series.dropna()
    cleaned = cleaned[cleaned.astype(str).str.strip() != ""]
    cleaned = cleaned[cleaned.astype(str).str.lower() != "nan"]
    
    # Split by comma and expand
    expanded_values = []
    for val in cleaned:
        val_str = str(val).strip()
        if ',' in val_str:
            # Split by comma and add each part
            parts = [p.strip() for p in val_str.split(',')]
            expanded_values.extend([p for p in parts if p])  # Filter empty parts
        else:
            expanded_values.append(val_str)
    
    return pd.Series(expanded_values)


def _prepare_value_counts(series: pd.Series, col1_name: str = "value", col2_name: str = "count") -> pd.DataFrame:
    """
    Get value counts after cleaning and splitting.
    
    Args:
        series: Series to count
        col1_name: Name for value column
        col2_name: Name for count column
        
    Returns:
        DataFrame with value counts
    """
    cleaned = _clean_and_split_values(series)
    if cleaned.empty:
        return pd.DataFrame()
    
    counts = cleaned.value_counts().reset_index()
    counts.columns = [col1_name, col2_name]
    return counts


# ===========================================================
# Chart Builders
# ===========================================================

def build_mortality_trend_chart(df: pd.DataFrame) -> Optional[Tuple[alt.Chart, pd.DataFrame]]:
    """
    Build mortality trend over time chart.
    
    Args:
        df: DataFrame with 'date' and 'mortality' columns
        
    Returns:
        Tuple of (chart, aggregated_data) or None if no valid data
    """
    # Only use records with valid dates for time-series
    df_valid = df[df["date"].notna()]
    trend_data = df_valid.groupby("date", as_index=False)["mortality"].sum()
    
    if trend_data.empty:
        return None
    
    chart = (
        alt.Chart(trend_data)
        .mark_line(point=True)
        .encode(
            x=alt.X("date:T", title="Date"),
            y=alt.Y("mortality:Q", title="Total Mortality"),
            tooltip=["date", "mortality"]
        )
        .properties(height=300)
    )
    
    return chart, trend_data


def build_cause_of_death_chart(df: pd.DataFrame) -> Optional[Tuple[alt.Chart, pd.DataFrame]]:
    """
    Build cause of death distribution bar chart.
    
    Args:
        df: DataFrame with 'cause_of_death' column
        
    Returns:
        Tuple of (chart, aggregated_data) or None if no valid data
    """
    cod_data = _prepare_value_counts(df["cause_of_death"], "cause", "count")
    
    if cod_data.empty:
        return None
    
    chart = (
        alt.Chart(cod_data)
        .mark_bar()
        .encode(
            x=alt.X("cause:N", sort="-y", title="Cause of Death"),
            y=alt.Y("count:Q", title="Count"),
            color=alt.Color("cause:N", legend=None),
            tooltip=["cause", "count"]
        )
        .properties(height=300)
    )
    
    return chart, cod_data


def build_life_stage_chart(df: pd.DataFrame) -> Optional[Tuple[alt.Chart, pd.DataFrame]]:
    """
    Build life stage distribution donut chart.
    
    Args:
        df: DataFrame with 'life_stage' column
        
    Returns:
        Tuple of (chart, aggregated_data) or None if no valid data
    """
    stage_data = _prepare_value_counts(df["life_stage"], "life_stage", "count")
    
    if stage_data.empty:
        return None
    
    chart = (
        alt.Chart(stage_data)
        .mark_arc(innerRadius=50)
        .encode(
            theta=alt.Theta("count:Q", title="Count"),
            color=alt.Color("life_stage:N", title="Life Stage"),
            tooltip=["life_stage", "count"]
        )
        .properties(height=300)
    )
    
    return chart, stage_data


def build_medium_condition_chart(df: pd.DataFrame) -> Optional[Tuple[alt.Chart, pd.DataFrame]]:
    """
    Build medium condition analysis bar chart.
    
    Args:
        df: DataFrame with 'medium_condition' column
        
    Returns:
        Tuple of (chart, aggregated_data) or None if no valid data
    """
    medium_data = _prepare_value_counts(df["medium_condition"], "medium_condition", "count")
    
    if medium_data.empty:
        return None
    
    chart = (
        alt.Chart(medium_data)
        .mark_bar()
        .encode(
            x=alt.X("medium_condition:N", sort="-y", title="Medium Condition"),
            y=alt.Y("count:Q", title="Count"),
            color=alt.Color("medium_condition:N", legend=None),
            tooltip=["medium_condition", "count"]
        )
        .properties(height=300)
    )
    
    return chart, medium_data


def build_egg_development_chart(df: pd.DataFrame) -> Optional[Tuple[alt.Chart, pd.DataFrame]]:
    """
    Build egg development status donut chart.
    
    Args:
        df: DataFrame with 'egg_development' column
        
    Returns:
        Tuple of (chart, aggregated_data) or None if no valid data
    """
    egg_data = _prepare_value_counts(df["egg_development"], "egg_development", "count")
    
    if egg_data.empty:
        return None
    
    chart = (
        alt.Chart(egg_data)
        .mark_arc(innerRadius=50)
        .encode(
            theta=alt.Theta("count:Q", title="Count"),
            color=alt.Color("egg_development:N", title="Egg Development"),
            tooltip=["egg_development", "count"]
        )
        .properties(height=300)
    )
    
    return chart, egg_data


def build_behavior_comparison_chart(df: pd.DataFrame) -> Optional[Tuple[alt.Chart, pd.DataFrame]]:
    """
    Build behavior comparison chart (pre vs post feeding).
    
    Args:
        df: DataFrame with 'behavior_pre' and 'behavior_post' columns
        
    Returns:
        Tuple of (chart, aggregated_data) or None if no valid data
    """
    # Clean and split both behavior columns
    pre_cleaned = _clean_and_split_values(df["behavior_pre"])
    post_cleaned = _clean_and_split_values(df["behavior_post"])
    
    if pre_cleaned.empty and post_cleaned.empty:
        return None
    
    # Get value counts
    pre_counts = pre_cleaned.value_counts() if not pre_cleaned.empty else pd.Series(dtype=int)
    post_counts = post_cleaned.value_counts() if not post_cleaned.empty else pd.Series(dtype=int)
    
    # Combine into dataframe
    behavior_data = pd.concat(
        [pre_counts.rename("count_pre"), post_counts.rename("count_post")], 
        axis=1
    ).fillna(0)
    
    if behavior_data.empty:
        return None
    
    behavior_data = behavior_data.reset_index().rename(columns={"index": "behavior"})
    behavior_data = behavior_data.melt("behavior", var_name="type", value_name="count")
    
    # Filter out zero counts
    behavior_data = behavior_data[behavior_data["count"] > 0]
    
    if behavior_data.empty:
        return None
    
    chart = (
        alt.Chart(behavior_data)
        .mark_bar()
        .encode(
            x=alt.X("behavior:N", sort="-y", title="Behavior"),
            y=alt.Y("count:Q", title="Count"),
            color=alt.Color("type:N", title="Timing",
                          scale=alt.Scale(
                              domain=["count_pre", "count_post"],
                              range=["#1f77b4", "#ff7f0e"]
                          )),
            tooltip=["behavior", "type", "count"]
        )
        .properties(height=300)
    )
    
    return chart, behavior_data


def build_mortality_by_stage_chart(df: pd.DataFrame) -> Optional[Tuple[alt.Chart, pd.DataFrame]]:
    """
    Build average mortality by life stage chart.
    
    Args:
        df: DataFrame with 'life_stage' and 'mortality' columns
        
    Returns:
        Tuple of (chart, aggregated_data) or None if no valid data
    """
    # Filter out empty life stages
    df_clean = df[df["life_stage"].notna()].copy()
    df_clean = df_clean[df_clean["life_stage"].astype(str).str.strip() != ""]
    df_clean = df_clean[df_clean["life_stage"].astype(str).str.lower() != "nan"]
    
    if df_clean.empty:
        return None
    
    # Handle comma-separated life stages
    expanded_rows = []
    for _, row in df_clean.iterrows():
        life_stage_str = str(row["life_stage"]).strip()
        if ',' in life_stage_str:
            # Split and create separate rows for each stage
            stages = [s.strip() for s in life_stage_str.split(',') if s.strip()]
            for stage in stages:
                expanded_rows.append({
                    "life_stage": stage,
                    "mortality": row["mortality"]
                })
        else:
            expanded_rows.append({
                "life_stage": life_stage_str,
                "mortality": row["mortality"]
            })
    
    if not expanded_rows:
        return None
    
    df_expanded = pd.DataFrame(expanded_rows)
    mort_stage_data = df_expanded.groupby("life_stage", as_index=False)["mortality"].mean()
    
    if mort_stage_data.empty:
        return None
    
    chart = (
        alt.Chart(mort_stage_data)
        .mark_bar()
        .encode(
            x=alt.X("life_stage:N", sort="-y", title="Life Stage"),
            y=alt.Y("mortality:Q", title="Average Mortality"),
            color=alt.Color("life_stage:N", legend=None),
            tooltip=["life_stage", alt.Tooltip("mortality:Q", format=".2f")]
        )
        .properties(height=300)
    )
    
    return chart, mort_stage_data


# ===========================================================
# Chart Registry (for easy iteration)
# ===========================================================

CHART_DEFINITIONS = [
    {
        "title": "🪦 Mortality Trends Over Time",
        "builder": build_mortality_trend_chart,
    },
    {
        "title": "☠️ Distribution of Causes of Death",
        "builder": build_cause_of_death_chart,
    },
    {
        "title": "🦠 Life Stage Distribution",
        "builder": build_life_stage_chart,
    },
    {
        "title": "🌊 Medium Condition Analysis",
        "builder": build_medium_condition_chart,
    },
    {
        "title": "🥚 Egg Development Status",
        "builder": build_egg_development_chart,
    },
    {
        "title": "🧠 Behavioral Comparison (Pre vs Post Feeding)",
        "builder": build_behavior_comparison_chart,
    },
    {
        "title": "⚰️ Mortality by Life Stage",
        "builder": build_mortality_by_stage_chart,
    },
]
