import streamlit as st
import pandas as pd
from sqlalchemy import text
from app.core import database


# ===========================================================
# PAGE: Connectivity Test with Safe Tab-Level Error Handling
# ===========================================================
def render():
    st.title("🧩 Daphnia Records Connection Test (Safe Mode)")
    st.caption("Verifying if records correctly connect to broods (per-set isolation with error capture)")

    # ---- Load cached broods metadata ----
    try:
        data = database.get_data()
        by_full = data.get("by_full", {})
        broods_df = pd.DataFrame.from_dict(by_full, orient="index")
        if "mother_id" not in broods_df.columns:
            broods_df["mother_id"] = broods_df.index

        broods_df = broods_df[
            [c for c in broods_df.columns if c in ["mother_id", "set_label", "assigned_person"]]
        ].copy()
    except Exception as e:
        st.error(f"❌ Failed to load broods cache: {e}")
        return

    # ---- Load records from Neon DB ----
    try:
        engine = database.get_engine()
        with engine.connect() as conn:
            records = pd.read_sql(text("SELECT * FROM records"), conn)
    except Exception as e:
        st.error(f"❌ Failed to load records table: {e}")
        return

    if records.empty:
        st.warning("⚠️ No records found in the database.")
        st.stop()

    # ---- Normalize IDs ----
    records["mother_id"] = records["mother_id"].astype(str).str.strip().str.upper()
    broods_df["mother_id"] = broods_df["mother_id"].astype(str).str.strip().str.upper()

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
