import os, json, re, hashlib, sqlite3, time
from datetime import datetime, timezone
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

SA_JSON = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
SHEET_ID = os.environ["GOOGLE_SHEET_ID"]
DB_PATH = os.environ.get("DB_PATH", "data/app.db")

# ── Tab filter & title parsing ────────────────────────────────────────────────
TAB_INCLUDE_PATTERN = re.compile(r"^set\s+[a-z]\b", re.IGNORECASE)
SET_TITLE_RE        = re.compile(r"^set\s+([a-z])(?:\s*\(([^)]*)\))?", re.IGNORECASE)

# Canonical columns for SQLite
CANON_COLS = [
    "mother_id", "hierarchy_id", "origin_mother_id",
    "n_i", "birth_date", "death_date", "n_f",
    "total_broods", "status", "notes",
    "set_label", "assigned_person",
]

# Header aliases (case/space/paren–insensitive) → canonical
ALIASES = {
    r"^mother\s*id(\s*\(pk\))?$": "mother_id",
    r"^hierarchy\s*id$": "hierarchy_id",
    r"^origin\s*mother\s*id(\s*\(fk\))?$": "origin_mother_id",
    r"^n\s*\(\s*i\s*\)$": "n_i",
    r"^birth\s*date$": "birth_date",
    r"^death\s*date$": "death_date",
    r"^n\s*\(\s*f\s*\)$": "n_f",
    r"^total\s*broods?$": "total_broods",
    r"^status$": "status",
    r"^notes?$": "notes",
}

# ── Logging helpers ───────────────────────────────────────────────────────────
def _log(msg): print(f"[ETL] {msg}", flush=True)
def _now_iso(): return datetime.now(timezone.utc).isoformat()
def _norm_header(h): return re.sub(r"\s+", " ", (h or "").strip()).lower()

# ── Sheet access ──────────────────────────────────────────────────────────────
def _authorize():
    creds = Credentials.from_service_account_info(
        json.loads(SA_JSON),
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    return gspread.authorize(creds)

def _fetch_tabs(gc):
    sh = gc.open_by_key(SHEET_ID)
    all_ws = sh.worksheets()
    use = [ws for ws in all_ws if TAB_INCLUDE_PATTERN.search(ws.title or "")]
    _log(f"Spreadsheet: {sh.title}; tabs discovered={len(all_ws)}; included={len(use)}")
    return sh, use

# ── Two-table slicing: keep only the right-hand table starting at MotherID ────
def _slice_to_right_table(values):
    """
    values: list[list[str]] from get_all_values()
    Return a new 2D list sliced from the FIRST column whose header startswith 'MotherID'.
    If not found, return [] so the tab is skipped.
    """
    if not values:
        return []
    headers = values[0]
    start_idx = None
    for i, h in enumerate(headers):
        if (h or "").strip().lower().startswith("motherid"):
            start_idx = i
            break
    if start_idx is None:
        return []
    return [row[start_idx:] for row in values]

# ── Header mapping & duplicate-column handling ────────────────────────────────
def _header_map(headers):
    normed = [_norm_header(h) for h in headers]
    m = {}
    for idx, nh in enumerate(normed):
        for pat, canon in ALIASES.items():
            if re.fullmatch(pat, nh or ""):
                # If duplicates exist, keep the FIRST match; we’ll collapse later if needed.
                if canon not in m:
                    m[canon] = headers[idx]
                break
    return m

def _pick_column_series(df, colname: str):
    """
    Return a 1D Series for colname even if duplicated headers exist.
    If duplicated, collapse row-wise: first non-empty wins; else empty string.
    """
    obj = df[colname]
    if isinstance(obj, pd.DataFrame):
        return obj.apply(
            lambda row: next((str(v).strip() for v in row if str(v).strip() != ""), ""),
            axis=1
        )
    return obj.astype(str).map(lambda v: v.strip())

def _to_int_or_none(x):
    try:
        if x is None or str(x).strip().lower() in ("", "nan", "null"):
            return None
        return int(float(str(x)))
    except Exception:
        return None

def _extract_set_info(title):
    m = SET_TITLE_RE.match(title or "")
    if not m:
        return "unknown", "unknown"
    letter = (m.group(1) or "").upper()
    person = (m.group(2) or "").strip() or "unknown"
    return letter, person

# ── Row cleaning ──────────────────────────────────────────────────────────────
def _clean(df, header_map):
    out = pd.DataFrame()

    # Sheet-sourced columns
    for canon in CANON_COLS:
        if canon in ("set_label", "assigned_person"):
            out[canon] = None
            continue
        if canon in header_map and header_map[canon] in df.columns:
            s = _pick_column_series(df, header_map[canon])
            out[canon] = s
        else:
            out[canon] = None

    # Int-ish fields
    for c in ("n_i", "n_f", "total_broods"):
        out[c] = out[c].map(_to_int_or_none)

    # Date text normalization
    for c in ("birth_date", "death_date"):
        out[c] = out[c].astype(str).map(lambda s: "" if s.strip().lower() in ("null","nan") else s.strip())

    # Primary key present
    out["mother_id"] = out["mother_id"].astype(str).map(lambda s: s.strip())
    out = out[out["mother_id"] != ""]
    return out

# ── Hash & SQLite writers ─────────────────────────────────────────────────────
def _hash_df(df):
    if "mother_id" in df.columns:
        df = df.sort_values("mother_id")
    return hashlib.md5(df.to_csv(index=False).encode("utf-8")).hexdigest()

def _ensure_meta(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS meta(
            k TEXT PRIMARY KEY,
            v TEXT NOT NULL
        )
    """)

def _write_mothers(conn, df):
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS mothers(
      mother_id TEXT PRIMARY KEY,
      hierarchy_id TEXT,
      origin_mother_id TEXT,
      n_i INTEGER,
      birth_date TEXT,
      death_date TEXT,
      n_f INTEGER,
      total_broods INTEGER,
      status TEXT,
      notes TEXT,
      set_label TEXT,
      assigned_person TEXT
    )""")
    cur.execute("DROP TABLE IF EXISTS mothers_tmp")
    cur.execute("""
    CREATE TABLE mothers_tmp(
      mother_id TEXT PRIMARY KEY,
      hierarchy_id TEXT,
      origin_mother_id TEXT,
      n_i INTEGER,
      birth_date TEXT,
      death_date TEXT,
      n_f INTEGER,
      total_broods INTEGER,
      status TEXT,
      notes TEXT,
      set_label TEXT,
      assigned_person TEXT
    )""")
    cur.executemany("""
    INSERT INTO mothers_tmp(
      mother_id,hierarchy_id,origin_mother_id,n_i,birth_date,death_date,
      n_f,total_broods,status,notes,set_label,assigned_person
    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", df[CANON_COLS].itertuples(index=False, name=None))
    cur.execute("DELETE FROM mothers")
    cur.execute("""INSERT INTO mothers
      SELECT mother_id,hierarchy_id,origin_mother_id,n_i,birth_date,death_date,
             n_f,total_broods,status,notes,set_label,assigned_person
      FROM mothers_tmp""")
    cur.execute("DROP TABLE mothers_tmp")
    conn.commit()

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    _log("Start ETL → mothers + meta (two-table slice; no caching logic)")
    gc = _authorize()
    sh, tabs = _fetch_tabs(gc)

    included, frames = [], []
    skipped_tabs = 0

    for ws in tabs:
        title, wid = ws.title, ws.id

        # Fetch with small retry
        values, err = None, None
        for i in range(3):
            try:
                values = ws.get_all_values(); break
            except Exception as e:
                err = e; time.sleep(1+i)

        if err and values is None:
            _log(f"Tab '{title}' read error: {err}"); skipped_tabs += 1; continue
        if not values:
            _log(f"Tab '{title}' empty; skipped."); skipped_tabs += 1; continue

        # 🔧 Keep only the right-hand table starting at 'MotherID'
        sliced = _slice_to_right_table(values)
        if not sliced:
            _log(f"Tab '{title}' skipped: no 'MotherID' header found (two-table slice).")
            skipped_tabs += 1
            continue

        headers = sliced[0]
        df = pd.DataFrame(sliced[1:], columns=headers) if len(sliced) > 1 else pd.DataFrame(columns=headers)

        hmap = _header_map(headers)
        if "mother_id" not in hmap:
            _log(f"Tab '{title}' skipped: missing MotherID column after slice.")
            skipped_tabs += 1
            continue

        cleaned = _clean(df, hmap)
        set_label, assignee = _extract_set_info(title)
        cleaned["set_label"] = set_label
        cleaned["assigned_person"] = assignee

        included.append({"title": title, "id": wid, "rows": int(len(cleaned)), "set": set_label, "assignee": assignee})
        frames.append(cleaned)
        _log(f"Tab '{title}' included: {len(cleaned)} rows.")

    _log(f"Tabs included: {len(included)}; tabs skipped: {skipped_tabs}")

    mothers = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=CANON_COLS)
    mothers = mothers.drop_duplicates(subset=["mother_id"], keep="last")
    content_hash = _hash_df(mothers)

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        _write_mothers(conn, mothers)
        _ensure_meta(conn)
        meta = {
            "last_refresh": _now_iso(),
            "row_count": len(mothers),
            "included_tabs": json.dumps(included, ensure_ascii=False),
            "source_sheet_id": SHEET_ID,
            "content_hash": content_hash,
            "schema": "mothers",
        }
        for k, v in meta.items():
            conn.execute(
                "INSERT INTO meta(k, v) VALUES(?, ?) "
                "ON CONFLICT(k) DO UPDATE SET v=excluded.v",
                (k, str(v))
            )
        conn.commit()
    finally:
        conn.close()

    _log(f"SQLite written: {DB_PATH}")
    _log("ETL done.")

if __name__ == "__main__":
    main()