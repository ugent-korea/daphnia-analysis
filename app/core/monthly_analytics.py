"""
Monthly analytics calculations for Daphnia breeding experiments.
Handles demographics, mortality, reproduction, survival analysis, and life stage transitions.
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import re


# ===========================================================
# Date Utilities
# ===========================================================

def parse_date_safe(date_str) -> Optional[pd.Timestamp]:
    """Safely parse date string to Timestamp."""
    if pd.isna(date_str):
        return None
    date_str = str(date_str).strip()
    if date_str.lower() in ('', 'unknown', 'null', 'nan', 'none', 'na', 'n/a'):
        return None
    try:
        return pd.to_datetime(date_str)
    except Exception:
        return None


def filter_records_by_month(records_df: pd.DataFrame, year: int, month: int) -> pd.DataFrame:
    """Filter records to a specific month."""
    records_df = records_df.copy()
    records_df['date_parsed'] = records_df['date'].apply(parse_date_safe)
    
    mask = (
        (records_df['date_parsed'].dt.year == year) & 
        (records_df['date_parsed'].dt.month == month)
    )
    
    return records_df[mask].copy()


# ===========================================================
# Demographics Analysis
# ===========================================================

def calculate_demographics(records_df: pd.DataFrame, broods_df: pd.DataFrame) -> Dict:
    """
    Calculate demographic statistics.
    
    Returns:
        Dictionary with counts and proportions by life stage, set, etc.
    """
    # Normalize life stages
    records_df = records_df.copy()
    records_df['life_stage_clean'] = records_df['life_stage'].fillna('').str.strip().str.lower()
    records_df.loc[records_df['life_stage_clean'] == 'adolescence', 'life_stage_clean'] = 'adolescent'
    
    # Count by life stage
    stage_counts = records_df['life_stage_clean'].value_counts().to_dict()
    stage_counts = {k: v for k, v in stage_counts.items() if k}  # Remove empty
    
    # Count by set
    set_counts = records_df['set_label'].value_counts().to_dict()
    
    # Unique mothers
    unique_mothers = records_df['mother_id'].nunique()
    
    # Age statistics (from broods table)
    broods_df = broods_df.copy()
    broods_df['birth_date_parsed'] = broods_df['birth_date'].apply(parse_date_safe)
    broods_df['age_days'] = (pd.Timestamp.now() - broods_df['birth_date_parsed']).dt.days
    
    age_stats = {
        'mean': broods_df['age_days'].mean() if not broods_df['age_days'].isna().all() else 0,
        'median': broods_df['age_days'].median() if not broods_df['age_days'].isna().all() else 0,
        'min': broods_df['age_days'].min() if not broods_df['age_days'].isna().all() else 0,
        'max': broods_df['age_days'].max() if not broods_df['age_days'].isna().all() else 0,
    }
    
    return {
        'stage_counts': stage_counts,
        'set_counts': set_counts,
        'unique_mothers': unique_mothers,
        'total_records': len(records_df),
        'age_stats': age_stats,
    }


# ===========================================================
# Mortality Analysis
# ===========================================================

def calculate_mortality_rates(records_df: pd.DataFrame) -> Dict:
    """
    Calculate mortality rates by life stage.
    
    Returns:
        Dictionary with mortality rates per stage
    """
    records_df = records_df.copy()
    records_df['life_stage_clean'] = records_df['life_stage'].fillna('').str.strip().str.lower()
    records_df.loc[records_df['life_stage_clean'] == 'adolescence', 'life_stage_clean'] = 'adolescent'
    
    # Filter valid life stages
    valid_stages = records_df[records_df['life_stage_clean'].isin(['neonate', 'adolescent', 'adult'])]
    
    if valid_stages.empty:
        return {}
    
    # Group by life stage and calculate total mortality
    mortality_by_stage = valid_stages.groupby('life_stage_clean')['mortality'].agg(['sum', 'count', 'mean']).to_dict('index')
    
    return mortality_by_stage


def analyze_mortality_causes(records_df: pd.DataFrame) -> pd.DataFrame:
    """
    Analyze causes of death with statistical relationships.
    
    Returns:
        DataFrame with cause analysis by life stage
    """
    records_df = records_df.copy()
    
    # Filter records with mortality
    mort_records = records_df[records_df['mortality'] > 0].copy()
    
    if mort_records.empty:
        return pd.DataFrame()
    
    # Normalize life stage
    mort_records['life_stage_clean'] = mort_records['life_stage'].fillna('').str.strip().str.lower()
    mort_records.loc[mort_records['life_stage_clean'] == 'adolescence', 'life_stage_clean'] = 'adolescent'
    
    # Clean cause of death
    mort_records['cause_clean'] = mort_records['cause_of_death'].fillna('unknown').str.strip().str.lower()
    
    # Group by life stage and cause
    cause_analysis = mort_records.groupby(['life_stage_clean', 'cause_clean']).agg({
        'mortality': 'sum',
        'mother_id': 'count'
    }).rename(columns={'mother_id': 'occurrences'}).reset_index()
    
    return cause_analysis


def analyze_mortality_trends(records_df: pd.DataFrame) -> Dict:
    """
    Analyze mortality trends across different dimensions.
    
    Returns:
        Dictionary with trend analysis results
    """
    records_df = records_df.copy()
    
    # Filter mortality events
    mort_records = records_df[records_df['mortality'] > 0].copy()
    
    if mort_records.empty:
        return {'has_data': False}
    
    # Normalize fields
    mort_records['life_stage_clean'] = mort_records['life_stage'].fillna('').str.strip().str.lower()
    mort_records.loc[mort_records['life_stage_clean'] == 'adolescence', 'life_stage_clean'] = 'adolescent'
    mort_records['cause_clean'] = mort_records['cause_of_death'].fillna('unknown').str.strip().str.lower()
    mort_records['medium_clean'] = mort_records['medium_condition'].fillna('unknown').str.strip().str.lower()
    
    # Cause by life stage
    cause_by_stage = mort_records.groupby(['life_stage_clean', 'cause_clean'])['mortality'].sum().unstack(fill_value=0)
    
    # Cause by medium condition
    cause_by_medium = mort_records.groupby(['medium_clean', 'cause_clean'])['mortality'].sum().unstack(fill_value=0)
    
    # Time trends (if date available)
    mort_records['date_parsed'] = mort_records['date'].apply(parse_date_safe)
    time_trend = mort_records.groupby(mort_records['date_parsed'].dt.date)['mortality'].sum()
    
    return {
        'has_data': True,
        'cause_by_stage': cause_by_stage.to_dict(),
        'cause_by_medium': cause_by_medium.to_dict(),
        'time_trend': time_trend.to_dict(),
        'total_deaths': int(mort_records['mortality'].sum()),
    }


# ===========================================================
# Reproduction Metrics
# ===========================================================

def calculate_reproduction_metrics(records_df: pd.DataFrame, broods_df: pd.DataFrame) -> Dict:
    """
    Calculate reproduction-related metrics.
    
    Returns:
        Dictionary with brood sizes, broods per mother, etc.
    """
    broods_df = broods_df.copy()
    
    # Brood size statistics
    brood_sizes = broods_df['n_i'].dropna()
    
    # Broods per mother (count children by origin_mother_id)
    broods_per_mother = broods_df.groupby('origin_mother_id').size()
    
    # Total broods field
    total_broods_stats = broods_df['total_broods'].dropna()
    
    return {
        'brood_size': {
            'mean': float(brood_sizes.mean()) if not brood_sizes.empty else 0,
            'median': float(brood_sizes.median()) if not brood_sizes.empty else 0,
            'min': int(brood_sizes.min()) if not brood_sizes.empty else 0,
            'max': int(brood_sizes.max()) if not brood_sizes.empty else 0,
            'total_neonates': int(brood_sizes.sum()) if not brood_sizes.empty else 0,
        },
        'broods_per_mother': {
            'mean': float(broods_per_mother.mean()) if not broods_per_mother.empty else 0,
            'median': float(broods_per_mother.median()) if not broods_per_mother.empty else 0,
            'max': int(broods_per_mother.max()) if not broods_per_mother.empty else 0,
        },
        'total_mothers': int(broods_df['mother_id'].nunique()),
        'total_broods': int(len(broods_df)),
    }


# ===========================================================
# Life Stage Transitions
# ===========================================================

def calculate_life_stage_transitions(records_df: pd.DataFrame) -> Dict:
    """
    Calculate average time for life stage transitions.
    
    Returns:
        Dictionary with transition times and flagged inconsistent broods
    """
    records_df = records_df.copy()
    records_df['date_parsed'] = records_df['date'].apply(parse_date_safe)
    records_df['life_stage_clean'] = records_df['life_stage'].fillna('').str.strip().str.lower()
    records_df.loc[records_df['life_stage_clean'] == 'adolescence', 'life_stage_clean'] = 'adolescent'
    
    # Sort by mother_id and date
    records_df = records_df.sort_values(['mother_id', 'date_parsed'])
    
    transitions = []
    flagged_broods = []
    
    # Group by mother_id
    for mother_id, group in records_df.groupby('mother_id'):
        stages = group[['date_parsed', 'life_stage_clean']].dropna()
        
        if stages.empty:
            continue
        
        # Find first occurrence of each stage
        first_neonate = stages[stages['life_stage_clean'] == 'neonate']['date_parsed'].min()
        first_adolescent = stages[stages['life_stage_clean'] == 'adolescent']['date_parsed'].min()
        first_adult = stages[stages['life_stage_clean'] == 'adult']['date_parsed'].min()
        
        # Check for inconsistencies (e.g., adult before adolescent)
        is_inconsistent = False
        
        if pd.notna(first_adolescent) and pd.notna(first_neonate) and first_adolescent < first_neonate:
            is_inconsistent = True
        if pd.notna(first_adult) and pd.notna(first_adolescent) and first_adult < first_adolescent:
            is_inconsistent = True
        if pd.notna(first_adult) and pd.notna(first_neonate) and first_adult < first_neonate:
            is_inconsistent = True
        
        if is_inconsistent:
            flagged_broods.append({
                'mother_id': mother_id,
                'reason': 'inconsistent_stage_order',
                'first_neonate': first_neonate,
                'first_adolescent': first_adolescent,
                'first_adult': first_adult,
            })
            continue  # Skip this brood
        
        # Calculate transitions
        if pd.notna(first_neonate) and pd.notna(first_adolescent):
            days = (first_adolescent - first_neonate).days
            if days >= 0:  # Valid transition
                transitions.append({
                    'mother_id': mother_id,
                    'transition': 'neonate_to_adolescent',
                    'days': days,
                })
        
        if pd.notna(first_adolescent) and pd.notna(first_adult):
            days = (first_adult - first_adolescent).days
            if days >= 0:
                transitions.append({
                    'mother_id': mother_id,
                    'transition': 'adolescent_to_adult',
                    'days': days,
                })
        
        if pd.notna(first_neonate) and pd.notna(first_adult):
            days = (first_adult - first_neonate).days
            if days >= 0:
                transitions.append({
                    'mother_id': mother_id,
                    'transition': 'neonate_to_adult',
                    'days': days,
                })
    
    # Calculate averages
    trans_df = pd.DataFrame(transitions)
    
    if trans_df.empty:
        return {
            'neonate_to_adolescent': None,
            'adolescent_to_adult': None,
            'neonate_to_adult': None,
            'flagged_broods': flagged_broods,
        }
    
    results = {}
    for trans_type in ['neonate_to_adolescent', 'adolescent_to_adult', 'neonate_to_adult']:
        subset = trans_df[trans_df['transition'] == trans_type]['days']
        if not subset.empty:
            results[trans_type] = {
                'mean': float(subset.mean()),
                'median': float(subset.median()),
                'min': int(subset.min()),
                'max': int(subset.max()),
                'count': int(len(subset)),
            }
        else:
            results[trans_type] = None
    
    results['flagged_broods'] = flagged_broods
    
    return results


# ===========================================================
# Reproduction Timing
# ===========================================================

def calculate_reproduction_timing(records_df: pd.DataFrame, broods_df: pd.DataFrame) -> Dict:
    """
    Calculate time to pregnancy and gestation period.
    
    Returns:
        Dictionary with pregnancy and gestation timing
    """
    records_df = records_df.copy()
    broods_df = broods_df.copy()
    
    # Parse dates
    records_df['date_parsed'] = records_df['date'].apply(parse_date_safe)
    records_df['life_stage_clean'] = records_df['life_stage'].fillna('').str.strip().str.lower()
    records_df.loc[records_df['life_stage_clean'] == 'adolescence', 'life_stage_clean'] = 'adolescent'
    
    # Normalize egg_development to yes/no
    records_df['egg_dev_clean'] = records_df['egg_development'].fillna('').str.strip().str.lower()
    
    broods_df['birth_date_parsed'] = broods_df['birth_date'].apply(parse_date_safe)
    
    # Sort by mother_id and date
    records_df = records_df.sort_values(['mother_id', 'date_parsed'])
    
    adult_to_pregnant = []
    pregnant_to_birth = []
    
    for mother_id, group in records_df.groupby('mother_id'):
        # Find first adult record
        adult_records = group[group['life_stage_clean'] == 'adult']
        if adult_records.empty:
            continue
        
        first_adult_date = adult_records['date_parsed'].min()
        
        # Find first pregnancy (egg_development = yes)
        pregnant_records = group[group['egg_dev_clean'] == 'yes']
        if not pregnant_records.empty:
            first_pregnant_date = pregnant_records['date_parsed'].min()
            
            # Adult to pregnant
            if pd.notna(first_adult_date) and pd.notna(first_pregnant_date) and first_pregnant_date >= first_adult_date:
                days = (first_pregnant_date - first_adult_date).days
                adult_to_pregnant.append({
                    'mother_id': mother_id,
                    'days': days,
                })
            
            # Pregnant to birth (find children's birth dates)
            children = broods_df[broods_df['origin_mother_id'] == mother_id]
            if not children.empty:
                for _, child in children.iterrows():
                    child_birth = child['birth_date_parsed']
                    if pd.notna(child_birth) and pd.notna(first_pregnant_date):
                        days = (child_birth - first_pregnant_date).days
                        if days >= 0:  # Valid gestation
                            pregnant_to_birth.append({
                                'mother_id': mother_id,
                                'child_id': child['mother_id'],
                                'days': days,
                            })
    
    # Calculate statistics
    results = {}
    
    if adult_to_pregnant:
        atp_df = pd.DataFrame(adult_to_pregnant)
        results['adult_to_pregnant'] = {
            'mean': float(atp_df['days'].mean()),
            'median': float(atp_df['days'].median()),
            'min': int(atp_df['days'].min()),
            'max': int(atp_df['days'].max()),
            'count': int(len(atp_df)),
        }
    else:
        results['adult_to_pregnant'] = None
    
    if pregnant_to_birth:
        ptb_df = pd.DataFrame(pregnant_to_birth)
        results['pregnant_to_birth'] = {
            'mean': float(ptb_df['days'].mean()),
            'median': float(ptb_df['days'].median()),
            'min': int(ptb_df['days'].min()),
            'max': int(ptb_df['days'].max()),
            'count': int(len(ptb_df)),
        }
    else:
        results['pregnant_to_birth'] = None
    
    return results


# ===========================================================
# Reproduction Timing V2 (with gestation yes→no logic and by-set breakdown)
# ===========================================================

def calculate_reproduction_timing_v2(records_df: pd.DataFrame) -> Dict:
    """
    Calculate reproduction timing by set with new gestation logic.
    Gestation = time from egg_development='yes' to egg_development='no'
    
    Returns:
        Dictionary with timing data by set
    """
    records_df = records_df.copy()
    
    # Parse dates
    records_df['date_parsed'] = records_df['date'].apply(parse_date_safe)
    records_df['life_stage_clean'] = records_df['life_stage'].fillna('').str.strip().str.lower()
    records_df.loc[records_df['life_stage_clean'] == 'adolescence', 'life_stage_clean'] = 'adolescent'
    
    # Normalize egg_development
    records_df['egg_dev_clean'] = records_df['egg_development'].fillna('').str.strip().str.lower()
    
    # Sort by mother_id and date
    records_df = records_df.sort_values(['mother_id', 'date_parsed'])
    
    adult_to_pregnant_by_set = {}
    gestation_by_set = {}
    
    for mother_id, group in records_df.groupby('mother_id'):
        set_label = group['set_label'].iloc[0] if 'set_label' in group.columns else 'unknown'
        
        # Find first adult record
        adult_records = group[group['life_stage_clean'] == 'adult']
        if adult_records.empty:
            continue
        
        first_adult_date = adult_records['date_parsed'].min()
        
        # Find first pregnancy (egg_development = yes)
        pregnant_records = group[group['egg_dev_clean'] == 'yes']
        if not pregnant_records.empty:
            first_pregnant_date = pregnant_records['date_parsed'].min()
            
            # Adult to pregnant
            if pd.notna(first_adult_date) and pd.notna(first_pregnant_date) and first_pregnant_date >= first_adult_date:
                days = (first_pregnant_date - first_adult_date).days
                
                if set_label not in adult_to_pregnant_by_set:
                    adult_to_pregnant_by_set[set_label] = []
                
                adult_to_pregnant_by_set[set_label].append({
                    'mother_id': mother_id,
                    'days': days
                })
            
            # Gestation: yes → no
            # Find first 'no' after this 'yes'
            records_after_yes = group[group['date_parsed'] > first_pregnant_date]
            first_no_after_yes = records_after_yes[records_after_yes['egg_dev_clean'] == 'no']['date_parsed'].min()
            
            if pd.notna(first_no_after_yes):
                days = (first_no_after_yes - first_pregnant_date).days
                if days >= 0 and days <= 10:  # Reasonable range (max 10 days)
                    if set_label not in gestation_by_set:
                        gestation_by_set[set_label] = []
                    
                    gestation_by_set[set_label].append({
                        'mother_id': mother_id,
                        'days': days
                    })
    
    # Calculate statistics by set
    results = {
        'adult_to_pregnant_by_set': {},
        'gestation_by_set': {}
    }
    
    for set_label, data_list in adult_to_pregnant_by_set.items():
        if data_list:
            df = pd.DataFrame(data_list)
            results['adult_to_pregnant_by_set'][set_label] = {
                'mean': float(df['days'].mean()),
                'median': float(df['days'].median()),
                'min': int(df['days'].min()),
                'max': int(df['days'].max()),
                'count': int(len(df))
            }
    
    for set_label, data_list in gestation_by_set.items():
        if data_list:
            df = pd.DataFrame(data_list)
            results['gestation_by_set'][set_label] = {
                'mean': float(df['days'].mean()),
                'median': float(df['days'].median()),
                'min': int(df['days'].min()),
                'max': int(df['days'].max()),
                'count': int(len(df))
            }
    
    return results


def prepare_survival_data(broods_df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare data for Kaplan-Meier survival analysis.
    
    Returns:
        DataFrame with survival data (duration, event, set_label)
    """
    broods_df = broods_df.copy()
    
    # Parse dates
    broods_df['birth_date_parsed'] = broods_df['birth_date'].apply(parse_date_safe)
    broods_df['death_date_parsed'] = broods_df['death_date'].apply(parse_date_safe)
    
    # Calculate survival time
    broods_df['survival_days'] = (broods_df['death_date_parsed'] - broods_df['birth_date_parsed']).dt.days
    
    # Determine if event occurred (death)
    broods_df['status_clean'] = broods_df['status'].fillna('').str.strip().str.lower()
    broods_df['event'] = broods_df['status_clean'].apply(lambda x: 1 if re.match(r'^dead$', x) else 0)
    
    # For alive broods, use current date as censoring time
    now = pd.Timestamp.now()
    broods_df.loc[broods_df['event'] == 0, 'survival_days'] = (
        now - broods_df.loc[broods_df['event'] == 0, 'birth_date_parsed']
    ).dt.days
    
    # Filter valid survival data
    survival_data = broods_df[
        (broods_df['survival_days'].notna()) & 
        (broods_df['survival_days'] >= 0)
    ][['mother_id', 'survival_days', 'event', 'set_label']].copy()
    
    return survival_data
