import os, sqlite3, re, datetime
import pandas as pd
from zoneinfo import ZoneInfo
import streamlit as st

DB_PATH = os.environ.get("DB_PATH", "data/database.db")

if not os.path.exists(DB_PATH):
    st.warning("Database not found. Running ETL refresh... this may take ~10–20s")
    from etl import refresh
    refresh.main()

# 🔑 ensure caches are reset and DB actually exists
st.cache_resource.clear()
st.cache_data.clear()

if not os.path.exists(DB_PATH):
    st.error(f"ETL did not create the database at {DB_PATH}")



@st.cache_resource
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

@st.cache_data(ttl=300)
def load_meta():
    conn = get_conn()
    try:
        cur = conn.execute("SELECT k,v FROM meta")
        return dict(cur.fetchall())
    except Exception:
        return {}

@st.cache_data(ttl=300)
def get_mother_row(mother_id):
    conn = get_conn()
    q = """
    SELECT mother_id,hierarchy_id,origin_mother_id,n_i,birth_date,death_date,
           n_f,total_broods,status,notes,set_label,assigned_person
    FROM mothers WHERE mother_id = ?
    """
    row = conn.execute(q, (mother_id,)).fetchone()
    if not row:
        return None
    cols = ["mother_id","hierarchy_id","origin_mother_id","n_i","birth_date","death_date",
            "n_f","total_broods","status","notes","set_label","assigned_person"]
    return dict(zip(cols, row))

@st.cache_data(ttl=300)
def get_children_ids(mother_id):
    conn = get_conn()
    q = "SELECT mother_id FROM mothers WHERE origin_mother_id = ?"
    return [r[0] for r in conn.execute(q, (mother_id,)).fetchall()]

def to_kst(dt_str: str):
    """Convert an ISO8601 UTC timestamp string to KST datetime string."""
    try:
        utc_dt = datetime.datetime.fromisoformat(dt_str)
        return utc_dt.astimezone(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S %Z")
    except Exception:
        return dt_str

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
    last_refresh = meta.get("last_refresh", "unknown")
    last_refresh_kst = to_kst(last_refresh) if last_refresh != "unknown" else "unknown"
    st.caption(f"Last refresh (KST): {last_refresh_kst} • rows: {meta.get('row_count', '?')} • schema: {meta.get('schema', 'mothers')}")

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
            if children:
                st.write(children)
            else:
                st.write("None")

if __name__ == "__main__":
    main()
