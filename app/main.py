import os, re, datetime
import streamlit as st
from sqlalchemy import create_engine, text
from zoneinfo import ZoneInfo  # stdlib Py3.9+

# --- DB bootstrap ---
DB_URL = os.environ.get("DATABASE_URL")
if not DB_URL:
    st.error("DATABASE_URL not configured in Streamlit Secrets / env.")
    st.stop()

@st.cache_resource
def get_engine():
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

# ---------- ID normalizers ----------
CORE_RE = re.compile(r'^([A-Za-z]+)(.*)$')

def canonical_core(s: str) -> str:
    """
    Accept inputs like 'E1', 'E1.2', 'E.1', 'E.1.2', 'e.01.002', 'E.1_0804'
    and return canonical dotted form 'E.1' / 'E.1.2'
    """
    s = (s or "").strip()
    s = s.split('_')[0]  # strip any date if present
    m = CORE_RE.match(s)
    if not m:
        raise ValueError(f"Bad core id: {s}")
    word = m.group(1).upper()
    rest = m.group(2)
    nums = re.findall(r'\d+', rest)
    if not nums:
        raise ValueError("Core must include at least one number, e.g. 'E.1'")
    nums = [str(int(n)) for n in nums]  # drop leading zeros
    return word + '.' + '.'.join(nums)

def alt_nodot_variant(core: str) -> str:
    """ 'E.1.2' -> 'E1.2' (remove the first dot) to match any legacy rows. """
    return re.sub(r'^([A-Za-z]+)\.', r'\1', core, count=1)

# ---------- Data access that tolerates core-only queries ----------
@st.cache_data(ttl=300)
def get_mother_row(user_input: str):
    """
    Accepts:
      - full id: 'E.1_0804' (or legacy 'E1_0804')
      - core only: 'E.1' / 'E1' (choose the latest by suffix)
    Returns (row_dict, resolved_full_id) or (None, None)
    """
    eng = get_engine()
    raw = (user_input or '').strip()
    if not raw:
        return None, None

    core = canonical_core(raw)                 # enforce dotted
    core_alt = alt_nodot_variant(core)         # legacy, no first dot
    has_suffix = '_' in raw
    suffix = raw.split('_', 1)[1] if has_suffix else None

    with eng.connect() as conn:
        if has_suffix:
            row = conn.execute(text("""
                SELECT mother_id,hierarchy_id,origin_mother_id,n_i,birth_date,death_date,
                       n_f,total_broods,status,notes,set_label,assigned_person
                FROM mothers
                WHERE split_part(mother_id,'_',1) IN (:core, :core_alt)
                  AND split_part(mother_id,'_',2) = :suf
                ORDER BY CASE WHEN split_part(mother_id,'_',1)=:core THEN 0 ELSE 1 END
                LIMIT 1
            """), {"core": core, "core_alt": core_alt, "suf": suffix}).fetchone()
        else:
            # pick latest by numeric MMDD (falls back to nulls-last)
            row = conn.execute(text("""
                SELECT mother_id,hierarchy_id,origin_mother_id,n_i,birth_date,death_date,
                       n_f,total_broods,status,notes,set_label,assigned_person
                FROM mothers
                WHERE split_part(mother_id,'_',1) IN (:core, :core_alt)
                ORDER BY NULLIF(split_part(mother_id,'_',2),'')::int DESC NULLS LAST,
                         mother_id DESC
                LIMIT 1
            """), {"core": core, "core_alt": core_alt}).fetchone()

    if not row:
        return None, None

    cols = ["mother_id","hierarchy_id","origin_mother_id","n_i","birth_date","death_date",
            "n_f","total_broods","status","notes","set_label","assigned_person"]
    d = dict(zip(cols, row))
    return d, d["mother_id"]

@st.cache_data(ttl=300)
def get_children_ids(parent_full_id: str):
    """Children are linked by full origin_mother_id (includes date)."""
    eng = get_engine()
    with eng.connect() as conn:
        q = text("SELECT mother_id FROM mothers WHERE origin_mother_id = :mid ORDER BY mother_id")
        return [r[0] for r in conn.execute(q, {"mid": parent_full_id}).all()]

# ---------- TEAM 2.0 generation rules ----------
ID_RE_TOP = re.compile(r'^([A-Za-z]+)\.?(\d+)(?:$|_)')

def _parse_core(core: str):
    core = canonical_core(core)           # force dotted
    parts = core.split('.')
    set_word = parts[0]
    gen = int(parts[1])
    path = [int(x) for x in parts[2:]]
    return set_word, gen, path

def _format_core(set_word, gen, path):
    s = f"{set_word}.{gen}"
    if path:
        s += "." + ".".join(map(str, path))
    return s

def _next_child_index(parent_core, child_ids):
    want = parent_core + '.'
    idx = []
    for cid in child_ids:
        ccore = cid.split('_')[0]
        if ccore.startswith(want):
            tail = ccore[len(want):]
            if re.fullmatch(r'\d+', tail):
                idx.append(int(tail))
    return (max(idx) + 1) if idx else 1

def _next_generation_for_set(eng, set_word):
    # Find existing top-level generations for this set (E.1, E.2, …) and return next
    with eng.connect() as conn:
        rows = conn.execute(text(
            "SELECT mother_id FROM mothers WHERE set_label = :s"
        ), {"s": set_word}).all()
    gens = []
    for (mid,) in rows:
        core = mid.split('_')[0]
        m = ID_RE_TOP.match(core)
        if not m:
            continue
        # exclude descendants (anything with a second dot after generation)
        if re.search(r'^[A-Za-z]+\.?\d+\.', core):
            continue
        gens.append(int(m.group(2)))
    next_gen = (max(gens) + 1) if gens else 2
    return f"{set_word}.{next_gen}"

def compute_child_and_discard(parent_row, child_ids, eng):
    # parent_row["mother_id"] may be legacy like 'E1_0804' — normalize core
    parent_core_raw = parent_row["mother_id"].split('_')[0]
    set_word, gen, path = _parse_core(parent_core_raw)
    parent_core = _format_core(set_word, gen, path)

    next_idx = _next_child_index(parent_core, child_ids)

    if len(path) == 0:
        # Founder/gen mother: no discard; just increment brood index
        suggested_core = _format_core(set_word, gen, [next_idx])
        return suggested_core, False, f"Founder {set_word}.{gen}: next brood={next_idx}."

    if next_idx <= 3:
        suggested_core = _format_core(set_word, gen, path + [next_idx])
        discard = next_idx in (1, 2)   # 1st & 2nd subbroods discarded; 3rd kept
        note = "discard (1st/2nd)" if discard else "keep (3rd)"
        return suggested_core, discard, f"{parent_core} subbrood {next_idx}: {note}."
    else:
        # 4th+ subbrood → becomes a NEW generation founder for this set
        new_gen = _next_generation_for_set(get_engine(), set_word)
        return new_gen, False, f"{parent_core} subbrood {next_idx} → new generation {new_gen}."

def today_suffix(tz="Asia/Seoul") -> str:
    # TEAM uses KST; change tz if you want another zone
    return datetime.datetime.now(ZoneInfo(tz)).strftime("_%m%d")

# ---------- UI ----------
def main():
    st.title("BEST LABS: Daphnia Magna TEAM 2.0")
    st.title("Daphnia Coding Protocol")
    meta = load_meta()
    st.caption(
        f"Last refresh (UTC): {meta.get('last_refresh','unknown')} • "
        f"rows: {meta.get('row_count','?')} • schema: {meta.get('schema','mothers')}"
    )

    mother_input = st.text_input(
        "Enter MotherID (core or full)", placeholder="e.g., E.1 or E.1_0804"
    ).strip()

    # Prefill with today; if cleared, we’ll still fall back to today
    date_append = st.text_input("Date suffix (_MMDD)", value=today_suffix())

    if mother_input:
        # tolerant lookup (core-only or full; dotted or legacy)
        parent, resolved_full_id = get_mother_row(mother_input)
        if not parent:
            st.error("MotherID not found.")
            return

        st.caption(
            f"Matched parent: `{resolved_full_id}` "
            f"(core normalized: `{canonical_core(resolved_full_id)}`)"
        )

        children = get_children_ids(resolved_full_id)
        suggested_core, should_discard, basis = compute_child_and_discard(
            parent, children, get_engine()
        )

        # Always include a date suffix; fallback to today's if the box is empty
        suffix = (date_append or "").strip() or today_suffix()
        final_child = suggested_core + suffix

        assigned = parent.get("assigned_person", "unknown") or "unknown"
        set_label = parent.get("set_label", "unknown") or "unknown"

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
