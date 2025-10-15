import base64, datetime, re
import pandas as pd
import streamlit as st
from zoneinfo import ZoneInfo

def set_faded_bg_from_svg(svg_path: str, overlay_alpha: float = 0.86,
                          img_width: str = "55vw", img_position: str = "center 8%"):
    with open(svg_path, "r", encoding="utf-8") as f:
        svg = f.read()
    b64 = base64.b64encode(svg.encode("utf-8")).decode()

    st.markdown(
        f"""
        <style>
        [data-testid="stHeader"] {{ background: transparent; }}
        .block-container {{ padding-top: 1rem; max-width: 900px; margin: 0 auto; }}
        .stApp {{
          background-image:
            linear-gradient(rgba(255,255,255,{overlay_alpha}), rgba(255,255,255,{overlay_alpha})),
            url("data:image/svg+xml;base64,{b64}");
          background-repeat: no-repeat, no-repeat;
          background-size: cover, {img_width} auto;
          background-position: center, {img_position};
          background-attachment: fixed, fixed;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

def today_suffix(tz="Asia/Seoul") -> str:
    return datetime.datetime.now(ZoneInfo(tz)).strftime("_%m%d")

def last_refresh_kst(meta) -> str:
    ts = (meta or {}).get("last_refresh")
    if not ts:
        return "unknown"
    s = ts.replace("Z", "+00:00")
    try:
        dt = datetime.datetime.fromisoformat(s)
        kst = dt.astimezone(ZoneInfo("Asia/Seoul"))
        return kst.strftime("%Y-%m-%d %H:%M:%S KST")
    except Exception:
        return ts


# ===========================================================
# Data Processing Utilities
# ===========================================================

CORE_RE = re.compile(r'^([A-Za-z]+)(.*)$')

def normalize_mother_id(mid: str) -> str:
    """Normalize mother_id to canonical format: LETTER.NUM.NUM_SUFFIX"""
    if not isinstance(mid, str):
        return ""
    
    mid = mid.strip().upper()
    if not mid:
        return ""
    
    # Split core and suffix
    parts = mid.split('_', 1)
    core = parts[0]
    suffix = parts[1] if len(parts) > 1 else ""
    
    # Parse core (e.g., "E.1.2" or "E1.2" or "E12")
    m = CORE_RE.match(core)
    if not m:
        return mid  # Return as-is if pattern doesn't match
    
    word = m.group(1).upper()
    nums = re.findall(r'\d+', m.group(2))
    
    if not nums:
        return mid  # No numbers found, return as-is
    
    # Normalize: remove leading zeros from each number
    nums = [str(int(n)) for n in nums]
    normalized_core = word + '.' + '.'.join(nums)
    
    # Reconstruct with suffix if present
    if suffix:
        return f"{normalized_core}_{suffix}"
    return normalized_core


def parse_date_safe(date_val):
    """Parse date, return NaT for NULL/empty values"""
    if pd.isna(date_val) or date_val == "" or date_val is None:
        return pd.NaT
    
    date_str = str(date_val).strip()
    if date_str.upper() in ["NULL", "NA", "N/A", "NONE", ""]:
        return pd.NaT
    
    # Try pandas auto-detection (handles YYYY-MM-DD, DD-MM-YYYY, etc.)
    try:
        return pd.to_datetime(date_str, errors='coerce')
    except:
        return pd.NaT


def merge_duplicate_columns(df: pd.DataFrame, column_base: str, 
                           suffix1: str = '_rec', suffix2: str = '_brood') -> pd.DataFrame:
    """
    Merge duplicate columns from dataframe merge operations.
    Prefers first suffix, falls back to second.
    """
    df = df.copy()
    col1 = f"{column_base}{suffix1}"
    col2 = f"{column_base}{suffix2}"
    
    if col1 in df.columns and col2 in df.columns:
        df[column_base] = df[col1].fillna(df[col2])
        df = df.drop(columns=[col1, col2])
    elif col1 in df.columns:
        df[column_base] = df[col1]
        df = df.drop(columns=[col1])
    elif col2 in df.columns:
        df[column_base] = df[col2]
        df = df.drop(columns=[col2])
    
    return df


def prepare_analysis_data(records: pd.DataFrame, broods: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare merged and cleaned data for analysis.
    
    Performs:
    - ID normalization
    - Merging records with broods metadata
    - Date parsing
    - Text cleaning
    - Mortality conversion
    """
    # Make copies to avoid modifying originals
    records = records.copy()
    broods = broods.copy()
    
    # Normalize IDs
    records["mother_id_original"] = records["mother_id"]
    broods["mother_id_original"] = broods["mother_id"]
    
    records["mother_id"] = records["mother_id"].map(normalize_mother_id)
    broods["mother_id"] = broods["mother_id"].map(normalize_mother_id)
    
    # Merge records with broods
    df = records.merge(
        broods, 
        on="mother_id", 
        how="left", 
        indicator=True, 
        suffixes=('_rec', '_brood')
    )
    
    # Handle duplicate columns from merge
    df = merge_duplicate_columns(df, "set_label")
    df = merge_duplicate_columns(df, "assigned_person")
    
    # Fill unknowns
    df["set_label"] = df["set_label"].fillna("Unknown")
    
    # Parse dates
    df["date"] = df["date"].apply(parse_date_safe)
    
    # Sort by date (NaT goes to end)
    df = df.sort_values("date", na_position='last')
    
    # Convert mortality to numeric
    df["mortality"] = pd.to_numeric(
        df.get("mortality", 0), 
        errors="coerce"
    ).fillna(0).astype(int)
    
    # Clean text columns
    text_cols = [
        "life_stage", "cause_of_death", "medium_condition",
        "egg_development", "behavior_pre", "behavior_post"
    ]
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.strip().str.lower()
    
    return df


def calculate_metrics(df: pd.DataFrame) -> dict:
    """Calculate summary metrics for a dataset."""
    total_records = len(df)
    unique_mothers = df["mother_id"].nunique()
    
    # Calculate life expectancy
    df_life = (
        df.groupby("mother_id")["date"]
        .agg(["min", "max"])
        .dropna()
        .assign(days_alive=lambda x: (x["max"] - x["min"]).dt.days)
    )
    
    avg_life_expectancy = (
        df_life["days_alive"].mean().round(1) 
        if not df_life.empty else 0
    )
    
    return {
        "total_records": total_records,
        "unique_mothers": unique_mothers,
        "avg_life_expectancy": avg_life_expectancy,
        "records_with_dates": df["date"].notna().sum(),
        "records_without_dates": df["date"].isna().sum(),
    }
