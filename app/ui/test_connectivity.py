import re
import streamlit as st
import pandas as pd
from app.core import database


# ===========================================================
# Helper: Normalize mother_id to canonical format
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


# ===========================================================
# PAGE: Connectivity Test with Safe Tab-Level Error Handling
# ===========================================================
def render():
    st.title("🧩 Daphnia Records Connection Test")
    st.caption("Verifying if records correctly connect to broods (per-set isolation with error capture)")

    # ---- Load cached broods metadata ----
    try:
        data = database.get_data()
        by_full = data.get("by_full", {})
        broods_df = pd.DataFrame.from_dict(by_full, orient="index")
        if "mother_id" not in broods_df.columns:
            broods_df["mother_id"] = broods_df.index
    except Exception as e:
        st.error(f"❌ Failed to load broods cache: {e}")
        return

    # ---- Load cached records ----
    try:
        records = database.get_records()
    except Exception as e:
        st.error(f"❌ Failed to load records table: {e}")
        return

    if records.empty:
        st.warning("⚠️ No records found in the database.")
        st.stop()

    # ---- Normalize IDs using canonical format ----
    records["mother_id"] = records["mother_id"].map(normalize_mother_id)
    broods_df["mother_id"] = broods_df["mother_id"].map(normalize_mother_id)

    # ---- Merge records ↔ broods ----
    try:
        df = records.merge(broods_df, on="mother_id", how="left")
    except Exception as e:
        st.error(f"❌ Merge failed: {e}")
        return

    # ---- Overview ----
    st.info(f"✅ Loaded {len(records):,} records | {len(broods_df):,} broods rows")
    st.caption(f"Columns in merged dataframe: {', '.join(df.columns)}")

    # ---- Identify all sets ----
    all_sets = sorted(df["set_label"].dropna().unique().tolist())
    if not all_sets:
        st.warning("⚠️ No set_label values found after merge — check broods metadata.")
        st.dataframe(df.head(), use_container_width=True)
        st.stop()

    # ---- Build tabs ----
    tabs = st.tabs(["🌍 Cumulative"] + [f"Set {s}" for s in all_sets])

    for i, tab in enumerate(tabs):
        with tab:
            try:
                if i == 0:
                    st.markdown("### 🌍 Cumulative Overview (All Sets Combined)")
                    subset = df
                else:
                    set_name = all_sets[i - 1]
                    st.markdown(f"### 🧬 Set {set_name} Overview")
                    subset = df[df["set_label"] == set_name]

                if subset.empty:
                    st.warning("⚠️ No records for this set.")
                else:
                    assigned_person = (
                        broods_df.loc[broods_df["set_label"] == set_name, "assigned_person"]
                        .dropna()
                        .unique()
                    )
                    person = assigned_person[0] if len(assigned_person) else "Unassigned"
                    st.caption(f"👩 Assigned to: **{person}**")

                    st.success(
                        f"Found **{len(subset):,} records** "
                        f"and **{subset['mother_id'].nunique():,} unique mothers**."
                    )

                    st.dataframe(
                        subset[
                            [c for c in subset.columns if c in ["mother_id", "set_label", "date", "mortality"]]
                        ].head(20),
                        use_container_width=True,
                    )

            except Exception as e:
                # Catch *any* tab-specific failure and display in red box
                st.error(f"❌ Error while loading this set: {type(e).__name__} — {e}")
                st.exception(e)
