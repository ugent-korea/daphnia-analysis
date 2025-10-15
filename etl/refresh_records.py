import os, json, re, hashlib, time, math
from datetime import datetime, timezone
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from sqlalchemy import create_engine, text

# ==== ENV ====
SA_JSON   = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
SHEET_ID  = os.environ["GOOGLE_SHEET_ID"]
DB_URL    = os.environ["DATABASE_URL"]

# ==== Tab filter & title parsing ====
TAB_INCLUDE_PATTERN = re.compile(r"^set\s+[a-z]\b", re.IGNORECASE)
SET_TITLE_RE        = re.compile(r"^set\s+([a-z])(?:\s*\(([^)]*)\))?", re.IGNORECASE)

# Canonical columns for DB
CANON_COLS = [
    "date", "life_stage", "mortality", "cause_of_death", "disease",
    "medium_condition", "egg_development", "behavior_pre", "behavior_post",
    "notes", "mother_id", "set_label", "assigned_person"
]

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

# ==== Two-table split ====
def _split_two_tables(values):
    """Split a full worksheet into left-hand (records) and right-hand (broods)."""
    if not values:
        return [], []
    headers = values[0]
    split_idx = None
    for i, h in enumerate(headers):
        if not h or str(h).strip() == "":
            split_idx = i
            break
    if split_idx is None:
        return values, []
    left = [row[:split_idx] for row in values]
    right = [row[split_idx + 1:] for row in values]
    return left, right

# ==== Header normalization ====
ALIASES = {
    r"^date$": "date",
    r"^(life\s*stage|lifestage)$": "life_stage",
    r"^mortality(\s*\(?\s*n\s*\)?)?$": "mortality",  # Matches: mortality, mortality(n), mortality (n)
    r"^cause\s*of\s*death$": "cause_of_death",
    r"^(sick|disease)$": "disease",  # Both "sick" and "disease" map to disease column
    r"^medium\s*condition$": "medium_condition",
    r"^egg\s*development$": "egg_development",
    r"^behavior\s*(prior|before)\s*(feeding|to\s*feeding)?$": "behavior_pre",
    r"^behavior\s*(post|after)\s*(feeding)?$": "behavior_post",
    r"^notes?$": "notes",
    r"^(mother\s*id|id\s*\(?\s*pk\s*\)?)$": "mother_id",  # Matches: mother id, motherid, id(pk), id (pk), ID(PK)
}

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

# ==== Utility ====
def _extract_set_info(title):
    m = SET_TITLE_RE.match(title or "")
    if not m:
        return "unknown", "unknown"
    letter = (m.group(1) or "").upper()
    person = (m.group(2) or "").strip() or "unknown"
    return letter, person

def _pick_column_series(df, colname):
    obj = df[colname]
    if isinstance(obj, pd.DataFrame):
        return obj.apply(lambda row: next((str(v).strip() for v in row if str(v).strip() != ""), ""), axis=1)
    return obj.astype(str).map(lambda v: v.strip())

# ==== DB schema ====
def _ensure_schema(conn):
    # Create table if not exists
    conn.execute(text("""
    CREATE TABLE IF NOT EXISTS records(
      id SERIAL PRIMARY KEY,
      date TEXT,
      life_stage TEXT,
      mortality INTEGER,
      cause_of_death TEXT,
      disease TEXT,
      medium_condition TEXT,
      egg_development TEXT,
      behavior_pre TEXT,
      behavior_post TEXT,
      notes TEXT,
      mother_id TEXT REFERENCES broods(mother_id),
      set_label TEXT,
      assigned_person TEXT
    )
    """))
    
    # Add set_label column if it doesn't exist (for old databases)
    conn.execute(text("""
    DO $$ 
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name='records' AND column_name='set_label'
        ) THEN
            ALTER TABLE records ADD COLUMN set_label TEXT;
        END IF;
    END $$;
    """))
    
    # Add assigned_person column if it doesn't exist (for old databases)
    conn.execute(text("""
    DO $$ 
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name='records' AND column_name='assigned_person'
        ) THEN
            ALTER TABLE records ADD COLUMN assigned_person TEXT;
        END IF;
    END $$;
    """))
    
    conn.execute(text("""
    CREATE TABLE IF NOT EXISTS meta(
      k TEXT PRIMARY KEY,
      v TEXT NOT NULL
    )
    """))

# ==== Data cleaning ====
def _clean(df, header_map):
    out = pd.DataFrame()
    for canon in ALIASES.values():
        if canon in header_map and header_map[canon] in df.columns:
            s = _pick_column_series(df, header_map[canon])
            out[canon] = s
        else:
            out[canon] = None
    out["mortality"] = pd.to_numeric(out["mortality"], errors="coerce").fillna(0).astype(int)
    out["mother_id"] = out["mother_id"].astype(str).str.strip()
    out = out[out["mother_id"] != ""]
    
    # CRITICAL: Normalize mother_id to canonical format (same as broods table)
    out["mother_id"] = out["mother_id"].map(_canonical_mother_id)
    out = out[out["mother_id"] != ""]  # Remove any that failed normalization
    
    return out

# ==== Hash ====
def _hash_df(df):
    return hashlib.md5(df.to_csv(index=False).encode("utf-8")).hexdigest()

# ==== Write ====
def _write_records(conn, df: pd.DataFrame):
    df_orig = df.copy()
    df = df.reindex(columns=CANON_COLS, fill_value=None)
    _log(f"Records before filtering: {len(df)}")
    
    valid_ids = {r[0] for r in conn.execute(text("SELECT mother_id FROM broods"))}
    _log(f"Valid mother_ids in broods table: {len(valid_ids)}")
    
    # Check for mismatches BEFORE filtering
    records_ids = set(df["mother_id"].dropna().unique())
    matching_ids = records_ids & valid_ids
    missing_ids = records_ids - valid_ids
    
    _log(f"Unique mother_ids in records: {len(records_ids)}")
    _log(f"Matching mother_ids: {len(matching_ids)}")
    _log(f"Missing mother_ids (not in broods): {len(missing_ids)}")
    
    if missing_ids:
        _log(f"Sample of missing IDs: {list(missing_ids)[:10]}")
    
    df = df[df["mother_id"].isin(valid_ids)]
    _log(f"Records after filtering by valid mother_ids: {len(df)}")
    
    if len(df) == 0:
        _log("WARNING: No records match valid mother_ids!")
        _log(f"Sample mother_ids from records (normalized): {list(records_ids)[:10]}")
        _log(f"Sample mother_ids from broods: {list(valid_ids)[:10]}")

    # Drop and recreate temp table with explicit schema (don't use LIKE which copies old schema)
    conn.execute(text("DROP TABLE IF EXISTS records_tmp"))
    conn.execute(text("""
    CREATE TABLE records_tmp(
      id SERIAL PRIMARY KEY,
      date TEXT,
      life_stage TEXT,
      mortality INTEGER,
      cause_of_death TEXT,
      disease TEXT,
      medium_condition TEXT,
      egg_development TEXT,
      behavior_pre TEXT,
      behavior_post TEXT,
      notes TEXT,
      mother_id TEXT,
      set_label TEXT,
      assigned_person TEXT
    )
    """))

    records = df.to_dict(orient="records")
    if records:
        conn.execute(text("""
            INSERT INTO records_tmp(
              date,life_stage,mortality,cause_of_death,disease,
              medium_condition,egg_development,behavior_pre,behavior_post,
              notes,mother_id,set_label,assigned_person
            )
            VALUES (
              :date,:life_stage,:mortality,:cause_of_death,:disease,
              :medium_condition,:egg_development,:behavior_pre,:behavior_post,
              :notes,:mother_id,:set_label,:assigned_person
            )
        """), records)

    conn.execute(text("TRUNCATE TABLE records"))
    conn.execute(text("""
        INSERT INTO records(
            date, life_stage, mortality, cause_of_death, disease,
            medium_condition, egg_development, behavior_pre, behavior_post,
            notes, mother_id, set_label, assigned_person
        )
        SELECT 
            date, life_stage, mortality, cause_of_death, disease,
            medium_condition, egg_development, behavior_pre, behavior_post,
            notes, mother_id, set_label, assigned_person
        FROM records_tmp
    """))
    conn.execute(text("DROP TABLE records_tmp"))
    
    _log(f"Successfully inserted {len(records)} records into database")

# ==== Main ====
def main():
    _log("Start ETL → records + meta (left-hand extraction)")

    gc = _authorize()
    sh, tabs = _fetch_tabs(gc)

    included, frames, skipped_tabs = [], [], 0

    for ws in tabs:
        title = ws.title
        try:
            values = ws.get_all_values()
        except Exception as e:
            _log(f"Tab '{title}' read error: {e}")
            skipped_tabs += 1
            continue
        if not values:
            _log(f"Tab '{title}' empty; skipped.")
            skipped_tabs += 1
            continue

        left, right = _split_two_tables(values)
        if not left or not left[0]:
            _log(f"Tab '{title}' skipped: no left-hand table found.")
            skipped_tabs += 1
            continue

        headers = left[0]
        df = pd.DataFrame(left[1:], columns=headers)
        hmap = _header_map(headers)
        
        # DEBUG: Log the headers we found
        _log(f"Tab '{title}' headers found: {headers}")
        _log(f"Tab '{title}' header mapping: {hmap}")
        
        if "mother_id" not in hmap:
            _log(f"Tab '{title}' skipped: missing MotherID.")
            skipped_tabs += 1
            continue

        cleaned = _clean(df, hmap)
        set_label, assignee = _extract_set_info(title)
        cleaned["set_label"] = set_label
        cleaned["assigned_person"] = assignee

        if not cleaned.empty:
            frames.append(cleaned)
        included.append({"title": title, "rows": len(cleaned), "set": set_label, "assignee": assignee})
        _log(f"Tab '{title}' included: {len(cleaned)} rows.")

    _log(f"Tabs included: {len(included)}; skipped: {skipped_tabs}")

    frames = [f for f in frames if not f.empty]
    records = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=CANON_COLS)
    records = records.drop_duplicates(subset=["date", "mother_id"], keep="last")

    engine = create_engine(DB_URL, pool_pre_ping=True)
    with engine.begin() as conn:
        _ensure_schema(conn)
        _write_records(conn, records)

        meta = {
            "records_last_refresh": _now_iso(),
            "records_row_count": str(len(records)),
            "records_included_tabs": json.dumps(included, ensure_ascii=False),
            "records_source_sheet_id": SHEET_ID,
            "records_content_hash": _hash_df(records),
            "records_schema": "records",
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
