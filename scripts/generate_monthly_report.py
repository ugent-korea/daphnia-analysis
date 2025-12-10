"""
Auto-generate monthly report for the previous month.
Run at the start of each month (e.g., on the 1st) to generate previous month's report.
"""

import sys
import os
from datetime import datetime
from calendar import month_name

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core import database, monthly_analytics, report_generator


def get_previous_month():
    """Get year and month for the previous month."""
    now = datetime.now()
    current_year = now.year
    current_month = now.month
    
    if current_month == 1:
        prev_month = 12
        prev_year = current_year - 1
    else:
        prev_month = current_month - 1
        prev_year = current_year
    
    return prev_year, prev_month


def generate_report_for_month(year: int, month: int, output_dir: str = "reports"):
    """
    Generate a complete monthly report and save to file.
    
    Args:
        year: Year of the report
        month: Month of the report (1-12)
        output_dir: Directory to save reports
    """
    
    print(f"\n{'='*60}")
    print(f"Generating Monthly Report: {month_name[month]} {year}")
    print(f"{'='*60}\n")
    
    # Load data
    print("📊 Loading data from database...")
    try:
        data = database.get_data()
        by_full = data.get("by_full", {})
        broods_df = __import__('pandas').DataFrame.from_dict(by_full, orient="index")
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
    
    # Filter for target month
    print(f"🔍 Filtering data for {month_name[month]} {year}...")
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
    
    print(f"✓ Filtered to {len(month_records)} records and {len(month_broods)} broods\n")
    
    if month_records.empty:
        print(f"⚠️  No data found for {month_name[month]} {year}")
        return False
    
    # Calculate all metrics
    print("📈 Calculating analytics...")
    demo = monthly_analytics.calculate_demographics(month_records, month_broods)
    mort = monthly_analytics.calculate_mortality_rates(month_records)
    repro = monthly_analytics.calculate_reproduction_metrics(month_records, month_broods)
    trans = monthly_analytics.calculate_life_stage_transitions(month_records)
    timing = monthly_analytics.calculate_reproduction_timing_v2(month_records)
    print("✓ Analytics calculated\n")
    
    # Generate narrative report
    print("📝 Generating narrative report...")
    month_label = f"{month_name[month]} {year}"
    
    report = f"""# Monthly Analytics Report
## {month_label}

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## Executive Summary

"""
    
    # Add key metrics
    total_deaths = sum(stage['sum'] for stage in mort.values()) if mort else 0
    
    report += f"""### Key Metrics

- **Total Population**: {demo['total_records']:,} recorded observations
- **Active Mothers**: {demo['unique_mothers']:,} unique breeding mothers
- **Neonates Born**: {repro['brood_size']['total_neonates']:,}
- **Total Deaths**: {int(total_deaths):,}
- **Mortality Rate**: {(total_deaths / sum(stage['count'] for stage in mort.values()) * 100):.2f}%
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
    report += f"*Report generated automatically by Daphnia Coding Protocol*\n"
    report += f"*Database last updated: {datetime.now().strftime('%Y-%m-%d')}*\n"
    
    print("✓ Report generated\n")
    
    # Save to file
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{year}_{month:02d}_{month_name[month]}_report.md"
    filepath = os.path.join(output_dir, filename)
    
    print(f"💾 Saving report to: {filepath}")
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"✓ Report saved successfully!\n")
    print(f"{'='*60}")
    print(f"Report Location: {os.path.abspath(filepath)}")
    print(f"{'='*60}\n")
    
    return True


def main():
    """Main function - generates report for previous month."""
    
    # Get previous month
    prev_year, prev_month = get_previous_month()
    
    print(f"\n🚀 Starting Monthly Report Generation")
    print(f"📅 Target: {month_name[prev_month]} {prev_year} (previous month)")
    
    # Generate report
    success = generate_report_for_month(prev_year, prev_month)
    
    if success:
        print("✅ Monthly report generation completed successfully!")
    else:
        print("❌ Monthly report generation failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
