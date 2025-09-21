import os, json, hashlib
from datetime import datetime, timezone
import pandas as pd
from sqlalchemy import create_engine, text

DB_URL = os.environ["DATABASE_URL"]

def _ensure_schema(conn):
    conn.execute(text("""
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
    )"""))
    conn.execute(text("""
    CREATE TABLE IF NOT EXISTS meta(
      k TEXT PRIMARY KEY,
      v TEXT NOT NULL
    )"""))

def _write_mothers(conn, df: pd.DataFrame):
    # stage → truncate → insert (transactional)
    conn.execute(text("DROP TABLE IF EXISTS mothers_tmp"))
    conn.execute(text("""
      CREATE TABLE mothers_tmp (LIKE mothers INCLUDING ALL)
    """))
    # bulk insert via SQLAlchemy executemany
    rows = df.to_records(index=False).tolist() if len(df) else []
    if rows:
        conn.execute(text("""
            INSERT INTO mothers_tmp(
              mother_id,hierarchy_id,origin_mother_id,n_i,birth_date,death_date,
              n_f,total_broods,status,notes,set_label,assigned_person
            ) VALUES (:mother_id,:hierarchy_id,:origin_mother_id,:n_i,:birth_date,:death_date,
                      :n_f,:total_broods,:status,:notes,:set_label,:assigned_person)
        """), [dict(zip(df.columns, r)) for r in df.itertuples(index=False, name=None)])
    conn.execute(text("TRUNCATE TABLE mothers"))
    conn.execute(text("""
      INSERT INTO mothers
      SELECT mother_id,hierarchy_id,origin_mother_id,n_i,birth_date,death_date,
             n_f,total_broods,status,notes,set_label,assigned_person
      FROM mothers_tmp
    """))
    conn.execute(text("DROP TABLE mothers_tmp"))

def _hash_df(df):
    if "mother_id" in df.columns:
        df = df.sort_values("mother_id")
    return hashlib.md5(df.to_csv(index=False).encode("utf-8")).hexdigest()

def main():
    # ... your sheet reading / cleaning → DataFrame `mothers` and `included`
    # assume you kept all your original code up to where you wrote SQLite
    # Here we only show the DB commit bit:

    engine = create_engine(DB_URL, pool_pre_ping=True)
    content_hash = _hash_df(mothers)

    with engine.begin() as conn:  # one transaction
        _ensure_schema(conn)
        _write_mothers(conn, mothers)

        meta = {
            "last_refresh": datetime.now(timezone.utc).isoformat(),
            "row_count": str(len(mothers)),
            "included_tabs": json.dumps(included, ensure_ascii=False),
            "source_sheet_id": os.environ["GOOGLE_SHEET_ID"],
            "content_hash": content_hash,
            "schema": "mothers",
        }
        for k, v in meta.items():
            conn.execute(text("""
              INSERT INTO meta(k, v) VALUES (:k, :v)
              ON CONFLICT (k) DO UPDATE SET v = EXCLUDED.v
            """), {"k": k, "v": v})

    print("[ETL] Postgres updated")

if __name__ == "__main__":
    main()
