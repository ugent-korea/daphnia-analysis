import os, re, datetime
from collections import defaultdict
from zoneinfo import ZoneInfo
from sqlalchemy import create_engine, text
import streamlit as st

DB_URL = os.getenv("DATABASE_URL") or st.secrets.get("DATABASE_URL")

def _ensure_db_or_stop():
    if not DB_URL:
        st.error("DATABASE_URL not configured in Streamlit Secrets / env.")
        st.stop()

@st.cache_resource
def get_engine():
    return create_engine(DB_URL, pool_pre_ping=True)

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

    by_full = {r["mother_id"]: dict(r) for r in moms}

    children_by_origin = defaultdict(list)
    for r in moms:
        if r["origin_mother_id"]:
            children_by_origin[r["origin_mother_id"]].append(r["mother_id"])

    core_latest = {}
    core_to_suffix = defaultdict(dict)
    for r in moms:
        core, suf, suf_i = core_and_suffix(r["mother_id"])
        core_to_suffix[core][suf] = r["mother_id"]
        best = core_latest.get(core)
        if best is None or suf_i > best[0]:
            core_latest[core] = (suf_i, r["mother_id"])

    set_max_gen = defaultdict(lambda: 1)
    for r in moms:
        core = canonical_core_local(r["mother_id"].split('_')[0])
        m = re.match(r'^([A-Za-z]+)\.(\d+)$', core)
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
    return load_all(_kst_day_key())
