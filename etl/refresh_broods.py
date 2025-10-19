import os, json, re, hashlib, time, math
from datetime import datetime, timezone
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from sqlalchemy import create_engine, text

# ==== ENV ====
SA_JSON   = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
SHEET_ID  = os.environ["DAPHNIA_GOOGLE_SHEET_ID"]
DB_URL    = os.environ["DAPHNIA_DATABASE_URL"]  # postgresql://... ?sslmode=require

# ==== Tab filter & title parsing ====
TAB_INCLUDE_PATTERN = re.compile(r"^set\s+[a-z]\b", re.IGNORECASE)
SET_TITLE_RE        = re.compile(r"^set\s+([a-z])(?:\s*\(([^)]*)\))?", re.IGNORECASE)

# Canonical columns for DB
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

# ==== Logging ====
def _log(msg): print(f"[ETL] {msg}", flush=True)
def _now_iso(): return datetime.now(timezone.utc).isoformat()
def _norm_header(h): return re.sub(r"\s+", " ", (h or "").strip()).lower()

# ==== Mother ID Normalization ====
def _canonical_mother_id(mid: str) -> str:
    """Normalize mother_id to canonical format: LETTER.NUM.NUM_SUFFIX"""
    if not mid or not isinstance(mid, str):
        return ""
    mid = mid.strip()
    if not mid:
        return ""
    
    # Split into core and suffix
    parts = mid.split('_', 1)
    core = parts[0]
    suffix = parts[1] if len(parts) > 1 else ""
    
    # Parse core (letter + numbers)
    m = re.match(r'^([A-Za-z]+)(.*)$', core)
    if not m:
        return mid  # Return as-is if doesn't match pattern
    
    letter = m.group(1).upper()
    nums_part = m.group(2)
    
    # Extract all numbers from the nums part
    nums = re.findall(r'\d+', nums_part)
    
    # Build canonical core
    if nums:
        canonical_core = letter + '.' + '.'.join(str(int(n)) for n in nums)
    else:
        canonical_core = letter
    
    # Reconstruct with suffix
    if suffix:
        return f"{canonical_core}_{suffix}"
    return canonical_core

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

# ==== Two-table slice (keep right-hand table starting at MotherID) ====
def _slice_to_right_table(values):
    if not values: return []
    headers = values[0]
    start_idx = None
    for i, h in enumerate(headers):
        if (h or "").strip().lower().startswith("motherid"):
            start_idx = i; break
    if start_idx is None: return []
    return [row[start_idx:] for row in values]

# ==== Header mapping & duplicate handling ====
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

# ==== Row cleaning ====
def _clean(df, header_map):
    out = pd.DataFrame()
    for canon in CANON_COLS:
        if canon in ("set_label", "assigned_person"):
            out[canon] = None
            continue
        if canon in header_map and header_map[canon] in df.columns:
            s = _pick_column_series(df, header_map[canon])
            out[canon] = s
        else:
            out[canon] = None

    for c in ("n_i", "n_f", "total_broods"):
        out[c] = out[c].map(_to_int_or_none)

    for c in ("birth_date", "death_date"):
        out[c] = out[c].astype(str).map(lambda s: "" if s.strip().lower() in ("null","nan") else s.strip())

    out["mother_id"] = out["mother_id"].astype(str).map(lambda s: s.strip())
    out = out[out["mother_id"] != ""]
    
    # Normalize mother_id to canonical format
    out["mother_id"] = out["mother_id"].map(_canonical_mother_id)
    out = out[out["mother_id"] != ""]  # Remove any that failed normalization
    
    # Also normalize origin_mother_id if present
    if "origin_mother_id" in out.columns:
        out["origin_mother_id"] = out["origin_mother_id"].astype(str).map(
            lambda s: _canonical_mother_id(s) if s and s.strip().lower() not in ("", "nan", "null") else None
        )
    
    return out

# ==== Hash & Postgres ====
def _hash_df(df):
    if "mother_id" in df.columns:
        df = df.sort_values("mother_id")
    return hashlib.md5(df.to_csv(index=False).encode("utf-8")).hexdigest()

def _ensure_schema(conn):
    conn.execute(text("""
    CREATE TABLE IF NOT EXISTS broods(
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
    )"""))
    conn.execute(text("""
    CREATE TABLE IF NOT EXISTS meta(
      k TEXT PRIMARY KEY,
      v TEXT NOT NULL
    )"""))

def _write_broods(conn, df: pd.DataFrame):
    df = df.reindex(columns=CANON_COLS, fill_value=None)
    for c in ("n_i", "n_f", "total_broods"):
        s = pd.to_numeric(df[c], errors="coerce")
        df[c] = [None if pd.isna(v) else int(v) for v in s]

    conn.execute(text("DROP TABLE IF EXISTS broods_tmp"))
    conn.execute(text("CREATE TABLE broods_tmp (LIKE broods INCLUDING ALL)"))

    records = []
    for rec in df.to_dict(orient="records"):
        for c in ("n_i", "n_f", "total_broods"):
            v = rec.get(c)
            if v is None:
                continue
            if isinstance(v, float) and math.isnan(v):
                rec[c] = None
            elif isinstance(v, float):
                rec[c] = int(v)
            elif isinstance(v, str) and v.strip() != "":
                try:
                    rec[c] = int(float(v))
                except Exception:
                    rec[c] = None
            elif hasattr(v, "item"):
                try:
                    rec[c] = int(v.item())
                except Exception:
                    rec[c] = None
        records.append(rec)

    if records:
        conn.execute(text("""
            INSERT INTO broods_tmp(
              mother_id,hierarchy_id,origin_mother_id,n_i,birth_date,death_date,
              n_f,total_broods,status,notes,set_label,assigned_person
            ) VALUES (
              :mother_id,:hierarchy_id,:origin_mother_id,:n_i,:birth_date,:death_date,
              :n_f,:total_broods,:status,:notes,:set_label,:assigned_person
            )
        """), records)

    conn.execute(text("TRUNCATE TABLE broods CASCADE"))
    conn.execute(text("""
      INSERT INTO broods
      SELECT mother_id,hierarchy_id,origin_mother_id,n_i,birth_date,death_date,
             n_f,total_broods,status,notes,set_label,assigned_person
      FROM broods_tmp
    """))
    conn.execute(text("DROP TABLE broods_tmp"))

# ==== Main ====
def main():
    _log("Start ETL → broods + meta (two-table slice; no caching logic)")

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

        sliced = _slice_to_right_table(values)
        if not sliced:
            _log(f"Tab '{title}' skipped: no 'MotherID' header found (two-table slice).")
            skipped_tabs += 1; continue

        headers = sliced[0]
        df = pd.DataFrame(sliced[1:], columns=headers) if len(sliced) > 1 else pd.DataFrame(columns=headers)

        hmap = _header_map(headers)
        if "mother_id" not in hmap:
            _log(f"Tab '{title}' skipped: missing MotherID column after slice.")
            skipped_tabs += 1; continue

        cleaned = _clean(df, hmap)
        set_label, assignee = _extract_set_info(title)
        cleaned["set_label"] = set_label
        cleaned["assigned_person"] = assignee

        if not cleaned.empty:
            frames.append(cleaned)
        included.append({"title": title, "rows": int(len(cleaned)), "set": set_label, "assignee": assignee})
        _log(f"Tab '{title}' included: {len(cleaned)} rows.")

    _log(f"Tabs included: {len(included)}; tabs skipped: {skipped_tabs}")

    frames = [f for f in frames if not f.empty]

    broods = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=CANON_COLS)
    broods = broods.drop_duplicates(subset=["mother_id"], keep="last")
    content_hash = _hash_df(broods)

    engine = create_engine(DB_URL, pool_pre_ping=True)
    with engine.begin() as conn:
        _ensure_schema(conn)
        _write_broods(conn, broods)

        meta = {
            "broods_last_refresh": _now_iso(),
            "broods_row_count": str(len(broods)),
            "broods_included_tabs": json.dumps(included, ensure_ascii=False),
            "broods_source_sheet_id": SHEET_ID,
            "broods_content_hash": content_hash,
            "broods_schema": "broods",
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
