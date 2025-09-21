import os, re, datetime
from collections import defaultdict
from zoneinfo import ZoneInfo

import streamlit as st
from sqlalchemy import create_engine, text

# ---------------- DB bootstrap ----------------
DB_URL = os.environ.get("DATABASE_URL")
if not DB_URL:
    st.error("DATABASE_URL not configured in Streamlit Secrets / env.")
    st.stop()

@st.cache_resource
def get_engine():
    return create_engine(DB_URL, pool_pre_ping=True)

# ---------------- Daily (KST) cache ----------------
def _kst_day_key() -> str:
    return datetime.datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y%m%d")

@st.cache_data(show_spinner=False)
def load_all(day_key: str):
    """Load ALL mothers + meta once per KST day and build fast in-memory indexes."""
    eng = get_engine()
    with eng.connect() as conn:
        moms = conn.execute(text("""
            SELECT mother_id,hierarchy_id,origin_mother_id,n_i,birth_date,death_date,
                   n_f,total_broods,status,notes,set_label,assigned_person
            FROM mothers
        """)).mappings().all()
        meta_rows = conn.execute(text("SELECT k,v FROM meta")).all()
        meta = {k: v for k, v in meta_rows}

    # ---- helpers for canonical cores ----
    CORE_RE = re.compile(r'^([A-Za-z]+)(.*)$')

    def canonical_core_local(s: str) -> str:
        s = (s or "").split('_')[0].strip()
        m = CORE_RE.match(s)
        if not m:
            return s
        word = m.group(1).upper()
        nums = re.findall(r'\d+', m.group(2))
        return word + ('.' + '.'.join(str(int(n)) for n in nums) if nums else "")

    def core_and_suffix(mid: str):
        core, suf = (mid.split('_', 1) + [""])[:2]
        core = canonical_core_local(core)
        suf_i = int(suf) if suf.isdigit() else -1
        return core, suf, suf_i

    # ---- indexes ----
    by_full = {r["mother_id"]: dict(r) for r in moms}

    children_by_origin = defaultdict(list)
    for r in moms:
        if r["origin_mother_id"]:
            children_by_origin[r["origin_mother_id"]].append(r["mother_id"])

    core_latest = {}                 # core -> (suffix_i, full_id)
    core_to_suffix = defaultdict(dict)  # core -> {suffix_str -> full_id}
    for r in moms:
        core, suf, suf_i = core_and_suffix(r["mother_id"])
        core_to_suffix[core][suf] = r["mother_id"]
        best = core_latest.get(core)
        if best is None or suf_i > best[0]:
            core_latest[core] = (suf_i, r["mother_id"])

    # max existing TOP-LEVEL generation per set (E.1, E.2, … only)
    set_max_gen = defaultdict(lambda: 1)
    for r in moms:
        core = canonical_core_local(r["mother_id"].split('_')[0])
        m = re.match(r'^([A-Za-z]+)\.(\d+)$', core)  # exactly one number → top-level
        if m:
            set_word, gen = m.group(1), int(m.group(2))
            set_max_gen[set_word] = max(set_max_gen[set_word], gen)

    return {
        "meta": meta,
        "by_full": by_full,
        "children_by_origin": dict(children_by_origin),
        "core_latest": {k: v[1] for k, v in core_latest.items()},
        "core_to_suffix": dict(core_to_suffix),
        "set_max_gen": dict(set_max_gen),
    }

def get_data():
    return load_all(_kst_day_key())  # cache invalidates automatically at KST midnight

# ---------------- ID normalizers (public) ----------------
CORE_RE = re.compile(r'^([A-Za-z]+)(.*)$')

def canonical_core(s: str) -> str:
    """
    Accept inputs like 'E1', 'E1.2', 'E.1', 'E.1.2', 'e.01.002', 'E.1_0804'
    and return canonical dotted form 'E.1' / 'E.1.2'
    """
    s = (s or "").strip()
    s = s.split('_')[0]
    m = CORE_RE.match(s)
    if not m:
        raise ValueError(f"Bad core id: {s}")
    word = m.group(1).upper()
    nums = re.findall(r'\d+', m.group(2))
    if not nums:
        raise ValueError("Core must include at least one number, e.g. 'E.1'")
    nums = [str(int(n)) for n in nums]
    return word + '.' + '.'.join(nums)

# ---------------- Cached lookups ----------------
def get_mother_row(user_input: str):
    """
    Accepts full id (E.1_0804 / E1_0804) or core only (E.1 / E1).
    Returns (row_dict, resolved_full_id) or (None, None)
    """
    data = get_data()
    raw = (user_input or "").strip()
    if not raw:
        return None, None

    try:
        core = canonical_core(raw)
    except Exception:
        return None, None

    if '_' in raw:
        suf = raw.split('_', 1)[1]
        full = data["core_to_suffix"].get(core, {}).get(suf)
        if not full:
            # last chance: exact full if the user typed it exactly as stored
            full = raw if raw in data["by_full"] else None
        if not full:
            return None, None
    else:
        full = data["core_latest"].get(core)
        if not full:
            return None, None

    return data["by_full"][full], full

def get_children_ids(parent_full_id: str):
    return get_data()["children_by_origin"].get(parent_full_id, [])

# ---------------- Final rules (A1 special; others use discard/keep/reset) ----------------
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

def _next_generation_for_set_cached(set_word: str) -> str:
    data = get_data()
    max_gen = data["set_max_gen"].get(set_word, 1)
    return f"{set_word}.{max_gen + 1}"

def _alive_count_in_set(set_word: str) -> int:
    """Count rows with status == 'Alive' (case-insensitive) within the same set."""
    data = get_data()
    cnt = 0
    for row in data["by_full"].values():
        if (row.get("set_label") or "").upper() == set_word.upper():
            if str(row.get("status", "")).strip().lower() == "alive":
                cnt += 1
    return cnt

def compute_child_and_discard(parent_row, child_ids):
    """
    A1 special:
      - If parent is exactly X.1, just suggest X.1.<k> (no discard/reset on A1 itself).
    Everyone else (any parent not exactly X.1):
      - 1st child → discard
      - 2nd child → discard if Alive(set) > 10, else keep
      - 3rd child → keep (experiments)
      - 4th+ child → RESET to next top-level X.(max+1)
    """
    # normalize the parent's core (strip date, enforce dotted)
    parent_core_raw = parent_row["mother_id"].split('_')[0]
    set_word, gen, path = _parse_core(parent_core_raw)
    parent_core = _format_core(set_word, gen, path)

    # A1 special: no discard/reset; children are A1.k
    if gen == 1 and len(path) == 0:
        next_idx = _next_child_index(parent_core, child_ids)
        suggested_core = f"{parent_core}.{next_idx}"
        return suggested_core, False, f"Founder {set_word}.1: next brood={next_idx} (no discard/reset on founder)."

    # Everyone else:
    next_idx = _next_child_index(parent_core, child_ids)

    if next_idx == 1:
        suggested_core = f"{parent_core}.1"
        return suggested_core, True, f"{parent_core}: 1st subbrood → discard."

    if next_idx == 2:
        alive_cnt = _alive_count_in_set(set_word)
        discard2 = alive_cnt > 10
        suggested_core = f"{parent_core}.2"
        reason = " (>10 Alive in set)" if discard2 else " (Alive ≤ 10)"
        return suggested_core, discard2, f"{parent_core}: 2nd subbrood → {'discard' if discard2 else 'keep'}{reason}. AliveCount={alive_cnt}"

    if next_idx == 3:
        suggested_core = f"{parent_core}.3"
        return suggested_core, False, f"{parent_core}: 3rd subbrood → keep (use for experiments)."

    # 4th and beyond → new top-level generation
    new_core = _next_generation_for_set_cached(set_word)
    return new_core, False, f"{parent_core}: {next_idx}th subbrood → RESET to new generation {new_core}."

# ---------------- Utilities ----------------
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
        return ts  # fallback

# ---------------- UI ----------------
def main():
    st.title("Daphnia Magna TEAM 2.0")
    st.title("Daphnia Coding Protocol")

    meta = get_data()["meta"]  # from daily cache
    st.caption(
        f"Last refresh (KST): {last_refresh_kst(meta)} • "
        f"rows: {meta.get('row_count','?')} • schema: Daphnia Broods"
    )

    mother_input = st.text_input(
        "Enter MotherID (core or full)", placeholder="e.g., E.1 or E.1_0804"
    ).strip()

    # Prefill with today; if cleared, fall back to today
    date_append = st.text_input("Date suffix (_MMDD)", value=today_suffix())

    if mother_input:
        parent, resolved_full_id = get_mother_row(mother_input)
        if not parent:
            st.error("MotherID not found.")
            return

        st.caption(
            f"Matched parent: `{resolved_full_id}` "
            f"(core normalized: `{canonical_core(resolved_full_id)}`)"
        )

        children = get_children_ids(resolved_full_id)  # from cache
        suggested_core, should_discard, basis = compute_child_and_discard(parent, children)

        # Always include a date suffix; fallback to today's if the box is empty
        suffix = (date_append or "").strip() or today_suffix()
        final_child = suggested_core + suffix

        assigned = parent.get("assigned_person", "unknown") or "unknown"
        set_label = parent.get("set_label", "unknown") or "unknown"

        st.subheader("Result")
        st.write(f"**Set:** {set_label} • **Assignee:** {assigned}")
        st.success(f"**Suggested Child ID:** {final_child}")
        if should_discard:
            st.error("Discard? Yes")
        else:
            st.write("**Discard?** No")

        st.caption(basis)

        with st.expander("Parent details"):
            st.json(parent)

        with st.expander("Existing children (origin = this MotherID)"):
            st.write(children if children else "None")

if __name__ == "__main__":
    main()
