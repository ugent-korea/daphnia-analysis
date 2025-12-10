"""
Auto-generate monthly reports for ALL months with data in the database.
Run after every database update to keep reports current with latest data.
"""

import sys
import os
from datetime import datetime
from calendar import month_name

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core import database, monthly_analytics, report_generator
import pandas as pd


def get_available_months(records_df: pd.DataFrame):
    """
    Detect all months that have data in the database.
    Returns list of (year, month) tuples.
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
    
    # Convert to list of tuples
    months = [(int(row['year']), int(row['month'])) for _, row in unique_months.iterrows()]
    
    return months


def generate_report_for_month(year: int, month: int, broods_df, records_df, output_dir: str = "reports"):
    """
    Generate a complete monthly report and save to file.
    
    Args:
        year: Year of the report
        month: Month of the report (1-12)
        broods_df: Broods dataframe
        records_df: Records dataframe
        output_dir: Directory to save reports
    """
    
    month_label = f"{month_name[month]} {year}"
    
    print(f"  Generating: {month_label}...", end=" ")
    
    # Filter for target month
    month_records = monthly_analytics.filter_records_by_month(records_df, year, month)
    month_broods = broods_df.copy()
    month_broods['birth_date_parsed'] = month_broods['birth_date'].apply(
        monthly_analytics.parse_date_safe
    )
    mask = (
        (month_broods['birth_date_parsed'].dt.year == year) &
        (month_broods['birth_date_parsed'].dt.month == month)
    )
    month_broods = month_broods[mask].copy()
    
    if month_records.empty:
        print(f"❌ No data")
        return False
    
    # Calculate all metrics
    demo = monthly_analytics.calculate_demographics(month_records, month_broods)
    mort = monthly_analytics.calculate_mortality_rates(month_records)
    repro = monthly_analytics.calculate_reproduction_metrics(month_records, month_broods)
    trans = monthly_analytics.calculate_life_stage_transitions(month_records)
    timing = monthly_analytics.calculate_reproduction_timing_v2(month_records)
    
    # Generate narrative report
    report = f"""# Monthly Analytics Report
## {month_label}

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## Executive Summary

"""
    
    # Add key metrics
    total_deaths = sum(stage['sum'] for stage in mort.values()) if mort else 0
    total_records = sum(stage['count'] for stage in mort.values()) if mort else demo['total_records']
    
    report += f"""### Key Metrics

- **Total Population**: {demo['total_records']:,} recorded observations
- **Active Mothers**: {demo['unique_mothers']:,} unique breeding mothers
- **Neonates Born**: {repro['brood_size']['total_neonates']:,}
- **Total Deaths**: {int(total_deaths):,}
- **Mortality Rate**: {(total_deaths / total_records * 100) if total_records > 0 else 0:.2f}%
- **Average Brood Size**: {repro['brood_size']['mean']:.1f} neonates
- **Average Age**: {demo['age_stats']['mean']:.1f} days

---

"""
    
    # Add auto-generated narrative
    narrative = report_generator.generate_executive_summary(
        demo, mort, repro, trans, month_label
    )
    report += narrative
    report += "\n\n---\n\n"
    
    # Add key findings
    findings = report_generator.generate_key_findings()
    report += findings
    report += "\n\n---\n\n"
    
    # Add detailed breakdowns
    report += "## Detailed Breakdowns\n\n"
    
    # Population by set
    report += "### Population by Experimental Set\n\n"
    for set_label, count in sorted(demo['set_counts'].items()):
        pct = (count / demo['total_records'] * 100)
        report += f"- **Set {set_label}**: {count:,} individuals ({pct:.1f}%)\n"
    
    report += "\n"
    
    # Mortality by stage
    if mort:
        report += "### Mortality by Life Stage\n\n"
        for stage in ['neonate', 'adolescent', 'adult']:
            if stage in mort:
                data = mort[stage]
                report += f"- **{stage.capitalize()}**: {int(data['sum'])} deaths ({data['percentage_of_total']:.1f}% of total)\n"
        report += "\n"
    
    # Reproduction timing
    if timing.get('adult_to_pregnant_by_set'):
        report += "### Time to Pregnancy by Set\n\n"
        for set_label in sorted(timing['adult_to_pregnant_by_set'].keys()):
            data = timing['adult_to_pregnant_by_set'][set_label]
            report += f"- **Set {set_label}**: {data['mean']:.1f} days (n={data['count']})\n"
        report += "\n"
    
    report += "\n---\n\n"
    report += f"*Report auto-generated by Daphnia Coding Protocol*\n"
    report += f"*Database last updated: {datetime.now().strftime('%Y-%m-%d')}*\n"
    
    # Save to file
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{year}_{month:02d}_{month_name[month]}_report.md"
    filepath = os.path.join(output_dir, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"✓ Done ({len(month_records)} records)")
    
    return True


def main():
    """Main function - generates reports for ALL months with data."""
    
    print(f"\n{'='*60}")
    print(f"Generating Reports for All Months")
    print(f"{'='*60}\n")
    
    # Load data
    print("📊 Loading data from database...")
    try:
        data = database.get_data()
        by_full = data.get("by_full", {})
        broods_df = pd.DataFrame.from_dict(by_full, orient="index")
        if "mother_id" not in broods_df.columns:
            broods_df["mother_id"] = broods_df.index
        
        records_df = database.get_records()
        print(f"✓ Loaded {len(records_df)} records and {len(broods_df)} broods\n")
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        return False
    
    if records_df.empty:
        print("⚠️  No records found in database")
        return False
    
    # Detect all months with data
    print("🔍 Detecting months with data...")
    available_months = get_available_months(records_df)
    
    if not available_months:
        print("⚠️  No months with data found")
        return False
    
    print(f"✓ Found {len(available_months)} months with data\n")
    
    # Generate report for each month
    print("📝 Generating reports:\n")
    
    success_count = 0
    for year, month in available_months:
        if generate_report_for_month(year, month, broods_df, records_df):
            success_count += 1
    
    print(f"\n{'='*60}")
    print(f"✅ Generated {success_count}/{len(available_months)} reports successfully")
    print(f"📁 Reports saved in: {os.path.abspath('reports/')}")
    print(f"{'='*60}\n")
    
    return success_count > 0


if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)
