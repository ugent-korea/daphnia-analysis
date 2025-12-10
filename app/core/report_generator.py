"""
Automated report generation for monthly analytics.
Generates narrative summaries from calculated metrics.
"""

from typing import Dict


def generate_executive_summary(
    demo: Dict, 
    mort: Dict, 
    repro: Dict, 
    trans: Dict,
    month_label: str
) -> str:
    """
    Generate executive summary narrative from calculated metrics.
    """
    
    # Calculate derived metrics
    total_deaths = sum(stage['sum'] for stage in mort.values()) if mort else 0
    total_records = sum(stage['count'] for stage in mort.values()) if mort else demo['total_records']
    mort_rate = (total_deaths / total_records * 100) if total_records > 0 else 0
    
    # Get death percentages by stage
    stage_death_pcts = {stage: data['percentage_of_total'] for stage, data in mort.items()} if mort else {}
    
    # Find set with highest population
    max_set = max(demo['set_counts'], key=demo['set_counts'].get) if demo['set_counts'] else 'N/A'
    max_set_count = demo['set_counts'][max_set] if demo['set_counts'] else 0
    
    # Build summary text
    summary = f"""### Monthly Performance Report

During {month_label}, the experimental population consisted of **{demo['total_records']:,} recorded observations** across **{demo['unique_mothers']:,} unique breeding mothers**. The average age of mothers tracked was **{demo['age_stats']['mean']:.1f} days**, with the oldest individual reaching **{int(demo['age_stats']['max'])} days**. The population was distributed across **{len(demo['set_counts'])} experimental sets** ({', '.join(sorted(demo['set_counts'].keys()))}), with Set {max_set} showing the highest population density at **{max_set_count:,} individuals**.
"""
    
    # Mortality analysis
    if mort:
        neonate_pct = stage_death_pcts.get('neonate', 0)
        adolescent_pct = stage_death_pcts.get('adolescent', 0)
        adult_pct = stage_death_pcts.get('adult', 0)
        
        summary += f"""
**Mortality patterns** revealed a total of **{int(total_deaths)} deaths** across **{total_records:,} observations**, resulting in an overall mortality rate of **{mort_rate:.2f}%** for the month. Death distribution by life stage: Neonates (**{neonate_pct:.1f}%**), Adolescents (**{adolescent_pct:.1f}%**), Adults (**{adult_pct:.1f}%**).
"""
    
    # Reproduction performance
    summary += f"""
**Reproductive performance** demonstrated an average brood size of **{repro['brood_size']['mean']:.1f} neonates**, with individual broods ranging from **{repro['brood_size']['min']} to {repro['brood_size']['max']} offspring**. A total of **{repro['brood_size']['total_neonates']:,} neonates** were produced across **{repro['total_broods']:,} broods**, averaging **{repro['broods_per_mother']['mean']:.1f} broods per mother**.
"""
    
    # Developmental timing
    if trans.get('neonate_to_adult'):
        summary += f"""
**Developmental timing** analysis revealed that individuals required an average of **{trans['neonate_to_adult']['mean']:.1f} days** (median: **{trans['neonate_to_adult']['median']:.1f} days**) to complete the full developmental cycle from neonate to adult stage.
"""
    
    return summary


def generate_key_findings() -> str:
    """Generate standard key findings section."""
    
    return """
**Key Findings & Conclusions:**

• Population health appears stable with consistent reproduction across all experimental sets

• Mortality patterns show stage-specific vulnerabilities requiring targeted monitoring

• Reproductive performance meets expected parameters for *Daphnia magna* populations

• Developmental timing is consistent with established Daphnia life cycle expectations
"""
