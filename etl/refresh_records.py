import os, json, re, hashlib, time, math
from datetime import datetime, timezone
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from sqlalchemy import create_engine, text

# ==== ENV ====
SA_JSON   = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
SHEET_ID  = os.environ["GOOGLE_SHEET_ID"]
DB_URL    = os.environ["DATABASE_URL"]  # postgresql://... ?sslmode=require

# ==== Tab filter & title parsing ====
TAB_INCLUDE_PATTERN = re.compile(r"^set\s+[a-z]\b", re.IGNORECASE)
SET_TITLE_RE        = re.compile(r"^set\s+([a-z])(?:\s*\(([^)]*)\))?", re.IGNORECASE)

# Canonical columns for RECORDS table
CANON_COLS = [
    "date", "life_stage", "mortality", "cause_of_death", "sick", "disease",
    "medium_condition", "egg_development", "behavior_pre", "behavior_post",
    "notes", "mother_id"
]

# Header aliases (case/space tolerant)
ALIASES = {
    r"^date$": "date",
    r"^id(\s*\(pk\))?$": "mother_id",
    r"^life\s*stage$": "life_stage",
    r"^mortality.*": "mortality",
    r"^cause\s*of\s*death$": "cause_of_death",
    r"^sick$": "sick",
    r"^disease$": "disease",
    r"^medium.*": "medium_condition",
    r"^egg\s*development$": "egg_development",
    r"^behavior.*prior.*": "behavior_pre",
    r"^behavior.*post.*": "behavior_post",
    r"^notes?$": "notes",
}

# ==== Logging ====
def _log(msg): print(f"[ETL] {msg}", flush=True)
def _now_iso(): return datetime.now(timezone.utc).isoformat()
def _norm_header(h): return re.sub(r"\s+", " ", (h or "").strip()).lower()

# ==== Sheets ====
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

# ==== Split logic (detect blank separator column) ====
def _split_two_tables(values):
    """Return (left_table, right_table) sliced by first blank header cell."""
    if not values:
        return [], []

    headers = values[0]
    split_idx = None
    for i, h in enumerate(headers):
        if not h or str(h).strip() == "":
            split_idx = i
            break

    if split_idx is None:
        return values, []  # only left table found

    left = [row[:split_idx] for row in values]
    right = [row[split_idx + 1 :] for row in values]
    return left, right

# ==== Header mapping ====
def _header_map(headers):
    normed = [_norm_header(h) for h in headers]
    m = {}
    for idx, nh in enumerate(normed):
        for pat, canon in ALIASES.items():
            if re.fullmatch(pat, nh or ""):
                if canon not in m:
                    m[canon] = headers[idx]
                break
    return m

def _pick_column_series(df, colname: str):
    obj = df[colname]
    if isinstance(obj, pd.DataFrame):
        return obj.apply(
            lambda row: next((str(v).strip() for v in row if str(v).strip() != ""), ""),
            axis=1
        )
    return obj.astype(str).map(lambda v: v.strip())

# ==== Type cleaning ====
def _to_int_or_none(x):
    try:
        if x is None or str(x).strip().lower() in ("", "nan", "null"):
            return None
        return int(float(str(x)))
    except Exception:
        return None

# ==== Row cleaning ====
def _clean(df, header_map):
    out = pd.DataFrame()
    for canon in CANON_COLS:
        if canon in header_map and header_map[canon] in df.columns:
            s = _pick_column_series(df, header_map[canon])
            out[canon] = s
        else:
            out[canon] = None

    # numeric normalization
    for c in ("mortality", "sick"):
        out[c] = out[c].map(_to_int_or_none)

    out["mother_id"] = out["mother_id"].astype(str).map(lambda s: s.strip())
    out = out[out["mother_id"] != ""]
    return out

# ==== Hash & Postgres ====
def _hash_df(df):
    if "mother_id" in df.columns:
        df = df.sort_values(["mother_id", "date"])
    return hashlib.md5(df.to_csv(index=False).encode("utf-8")).hexdigest()

def _ensure_schema(conn):
    conn.execute(text("""
    CREATE TABLE IF NOT EXISTS records(
      id SERIAL PRIMARY KEY,
      date TEXT,
      life_stage TEXT,
      mortality INTEGER,
      cause_of_death TEXT,
      sick INTEGER,
      disease TEXT,
      medium_condition TEXT,
      egg_development TEXT,
      behavior_pre TEXT,
      behavior_post TEXT,
      notes TEXT,
      mother_id TEXT REFERENCES broods(mother_id)
    )
    """))
    conn.execute(text("""
    CREATE TABLE IF NOT EXISTS meta(
      k TEXT PRIMARY KEY,
      v TEXT NOT NULL
    )"""))

def _write_records(conn, df: pd.DataFrame):
    if df.empty:
        _log("No records to insert.")
        return

    df = df.reindex(columns=CANON_COLS, fill_value=None)

    # --- numeric cleanup ---
    for c in ("mortality", "sick"):
        s = pd.to_numeric(df[c], errors="coerce")
        df[c] = [None if pd.isna(v) or v > 2_000_000_000 or v < -2_000_000_000 else int(v) for v in s.fillna(0)]

    # --- remove records with invalid mother_id ---
    valid_ids = {r[0] for r in conn.execute(text("SELECT mother_id FROM broods"))}
    before = len(df)
    df = df[df["mother_id"].isin(valid_ids)]
    dropped = before - len(df)
    if dropped:
        _log(f"Skipped {dropped} rows with invalid mother_id not found in broods.")

    # --- continue as before ---
    conn.execute(text("DROP TABLE IF EXISTS records_tmp"))
    conn.execute(text("CREATE TABLE records_tmp (LIKE records INCLUDING ALL)"))

    records = df.to_dict(orient="records")
    if records:
        conn.execute(
            text(f"""
                INSERT INTO records_tmp(
                  {', '.join(CANON_COLS)}
                ) VALUES (
                  {', '.join(':'+c for c in CANON_COLS)}
                )
            """),
            records
        )

    conn.execute(text("TRUNCATE TABLE records"))
    conn.execute(text("INSERT INTO records SELECT * FROM records_tmp"))
    conn.execute(text("DROP TABLE records_tmp"))

def _extract_set_info(title):
    """Extract set label (e.g., 'E') and assigned person from tab title."""
    m = re.match(r"^set\s+([a-z])(?:\s*\(([^)]*)\))?", title or "", re.IGNORECASE)
    if not m:
        return "unknown", "unknown"
    letter = (m.group(1) or "").upper()
    person = (m.group(2) or "").strip() or "unknown"
    return letter, person


# ==== Main ====
def main():
    _log("Start ETL → records + meta (split two-table sheet; left-hand extraction)")

    gc = _authorize()
    sh, tabs = _fetch_tabs(gc)

    included, frames, skipped_tabs = [], [], 0

    for ws in tabs:
        title = ws.title
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

        left, right = _split_two_tables(values)
        if not left:
            _log(f"Tab '{title}' skipped: no left-hand table (Date-based).")
            skipped_tabs += 1; continue

        headers = left[0]
        df = pd.DataFrame(left[1:], columns=headers) if len(left) > 1 else pd.DataFrame(columns=headers)

        hmap = _header_map(headers)
        if "mother_id" not in hmap:
            _log(f"Tab '{title}' skipped: missing ID column after split.")
            skipped_tabs += 1; continue

        cleaned = _clean(df, hmap)
        set_label, assignee = _extract_set_info(title)
        cleaned["set_label"] = set_label
        cleaned["assigned_person"] = assignee

        if not cleaned.empty:
            frames.append(cleaned)
        included.append({"title": title, "rows": int(len(cleaned)), "set": set_label, "assignee": assignee})
        _log(f"Tab '{title}' included: {len(cleaned)} record rows.")

    _log(f"Tabs included: {len(included)}; tabs skipped: {skipped_tabs}")

    frames = [f for f in frames if not f.empty]
    records = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=CANON_COLS)
    content_hash = _hash_df(records)

    engine = create_engine(DB_URL, pool_pre_ping=True)
    with engine.begin() as conn:
        _ensure_schema(conn)
        _write_records(conn, records)

        meta = {
            "last_refresh": _now_iso(),
            "row_count": str(len(records)),
            "included_tabs": json.dumps(included, ensure_ascii=False),
            "source_sheet_id": SHEET_ID,
            "content_hash": content_hash,
            "schema": "records",
        }
        for k, v in meta.items():
            conn.execute(text("""
              INSERT INTO meta(k, v) VALUES (:k, :v)
              ON CONFLICT (k) DO UPDATE SET v = EXCLUDED.v
            """), {"k": k, "v": v})

    _log("[ETL] Postgres updated")
    _log("ETL done.")

if __name__ == "__main__":
    main()
