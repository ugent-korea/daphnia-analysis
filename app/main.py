import os, re, datetime
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

DB_URL = os.environ.get("DATABASE_URL")  # e.g., neon url with sslmode=require
if not DB_URL:
    st.stop()  # or raise

@st.cache_resource
def get_engine():
    # Pool pre_ping avoids stale connections in serverless
    return create_engine(DB_URL, pool_pre_ping=True)

@st.cache_data(ttl=300)
def load_meta():
    eng = get_engine()
    try:
        with eng.connect() as conn:
            rows = conn.execute(text("SELECT k, v FROM meta")).all()
        return {k: v for k, v in rows}
    except Exception:
        return {}

@st.cache_data(ttl=300)
def get_mother_row(mother_id):
    eng = get_engine()
    q = text("""
        SELECT mother_id,hierarchy_id,origin_mother_id,n_i,birth_date,death_date,
               n_f,total_broods,status,notes,set_label,assigned_person
        FROM mothers WHERE mother_id = :mid
    """)
    with eng.connect() as conn:
        row = conn.execute(q, {"mid": mother_id}).fetchone()
    if not row:
        return None
    cols = ["mother_id","hierarchy_id","origin_mother_id","n_i","birth_date","death_date",
            "n_f","total_broods","status","notes","set_label","assigned_person"]
    return dict(zip(cols, row))

@st.cache_data(ttl=300)
def get_children_ids(mother_id):
    eng = get_engine()
    q = text("SELECT mother_id FROM mothers WHERE origin_mother_id = :mid")
    with eng.connect() as conn:
        return [r[0] for r in conn.execute(q, {"mid": mother_id}).all()]

def compute_child_and_discard(parent_mother_row, child_ids):
    parent_prefix = str(parent_mother_row["mother_id"]).split("_")[0]
    conforming_idx, nonconforming = [], 0
    for cid in child_ids:
        cprefix = str(cid).split("_")[0]
        if cprefix.startswith(parent_prefix + "."):
            tail = cprefix[len(parent_prefix) + 1:]
            if re.fullmatch(r"\d+", tail):
                conforming_idx.append(int(tail))
            else:
                nonconforming += 1
        else:
            nonconforming += 1
    max_idx = max(conforming_idx) if conforming_idx else 0
    next_idx = max_idx + 1
    suggested_child_id = f"{parent_prefix}.{next_idx}"

    status_norm = str(parent_mother_row.get("status","")).strip().lower()
    death_norm = str(parent_mother_row.get("death_date","")).strip()
    not_alive = (status_norm != "alive") and (status_norm != "")
    has_death_date = (death_norm != "") and (death_norm.lower() != "null")
    should_discard = bool(not_alive or has_death_date)

    basis_bits = [f"children={len(child_ids)}", f"conforming_max={max_idx}"]
    if nonconforming: basis_bits.append(f"nonconforming={nonconforming}")
    if should_discard:
        reasons=[]
        if not_alive: reasons.append(f"status={parent_mother_row.get('status','')}")
        if has_death_date: reasons.append(f"death_date={parent_mother_row.get('death_date','')}")
        if reasons: basis_bits.append("discard_reasons=" + ";".join(reasons))
    basis = "; ".join(basis_bits)
    return suggested_child_id, should_discard, basis

def main():
    st.title("Mother → Child ID (compute on read)")
    meta = load_meta()
    st.caption(f"Last refresh (UTC): {meta.get('last_refresh','unknown')} • rows: {meta.get('row_count','?')} • schema: {meta.get('schema','mothers')}")

    mother_input = st.text_input("Enter MotherID", placeholder="e.g., E.1_0804").strip()
    date_append = st.text_input("Optional date suffix (_MMDD)", value=datetime.datetime.now().strftime("_%m%d"))

    if mother_input:
        parent = get_mother_row(mother_input)
        if not parent:
            st.error("MotherID not found.")
            return

        children = get_children_ids(mother_input)
        suggested_prefix, should_discard, basis = compute_child_and_discard(parent, children)

        assigned = parent.get("assigned_person","unknown") or "unknown"
        set_label = parent.get("set_label","unknown") or "unknown"

        final_child = suggested_prefix + date_append if date_append else suggested_prefix

        st.subheader("Result")
        st.write(f"**Set:** {set_label} • **Assignee:** {assigned}")
        st.success(f"**Suggested Child ID:** {final_child}")
        st.write(f"**Discard?** {'Yes' if should_discard else 'No'}")
        st.caption(basis)

        with st.expander("Parent details"):
            st.json(parent)

        with st.expander("Existing children (origin = this MotherID)"):
            st.write(children if children else "None")

if __name__ == "__main__":
    main()
