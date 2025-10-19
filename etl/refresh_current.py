import os
from datetime import datetime, timezone
from sqlalchemy import create_engine, text

# ==== ENV ====
DB_URL = os.environ["DAPHNIA_DATABASE_URL"]

# ==== Logging ====
def _log(msg): print(f"[ETL-CURRENT] {msg}", flush=True)
def _now_iso(): return datetime.now(timezone.utc).isoformat()

# ==== Schema ====
def _ensure_schema(conn):
    """Create current table if it doesn't exist."""
    conn.execute(text("""
    CREATE TABLE IF NOT EXISTS current(
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
      assigned_person TEXT,
      brooder TEXT
    )
    """))
    
    # Add brooder column if it doesn't exist (for old databases)
    conn.execute(text("""
    DO $$ 
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name='current' AND column_name='brooder'
        ) THEN
            ALTER TABLE current ADD COLUMN brooder TEXT;
        END IF;
    END $$;
    """))
    
    _log("Schema ensured: current table exists with brooder column")

# ==== Main Logic ====
def main():
    _log("Start ETL → current (alive broods with latest records)")
    
    engine = create_engine(DB_URL, pool_pre_ping=True)
    
    with engine.begin() as conn:
        # Ensure schema exists
        _ensure_schema(conn)
        
        # Step 1: Get all alive mother_ids from broods
        # Alive = death_date is NULL/empty AND status does NOT indicate death
        alive_query = text("""
            SELECT mother_id 
            FROM broods 
            WHERE (death_date IS NULL OR death_date = '' OR TRIM(death_date) = '')
              AND (status IS NULL OR status = '' 
                   OR LOWER(TRIM(status)) NOT IN ('dead', 'deceased', 'died'))
        """)
        
        alive_broods = conn.execute(alive_query).fetchall()
        alive_mother_ids = [row[0] for row in alive_broods]
        
        _log(f"Found {len(alive_mother_ids)} alive broods")
        
        if not alive_mother_ids:
            _log("No alive broods found. Truncating current table.")
            conn.execute(text("TRUNCATE TABLE current"))
            _log("ETL done.")
            return
        
        # Step 2: For each alive mother_id, get the most recent record
        # We'll use a single query with window function for efficiency
        latest_records_query = text("""
            WITH ranked_records AS (
                SELECT 
                    r.*,
                    ROW_NUMBER() OVER (PARTITION BY r.mother_id ORDER BY r.date DESC) as rn
                FROM records r
                WHERE r.mother_id = ANY(:mother_ids)
            )
            SELECT 
                date, life_stage, mortality, cause_of_death, disease,
                medium_condition, egg_development, behavior_pre, behavior_post,
                notes, mother_id, set_label, assigned_person, brooder
            FROM ranked_records
            WHERE rn = 1
        """)
        
        latest_records = conn.execute(
            latest_records_query, 
            {"mother_ids": alive_mother_ids}
        ).mappings().all()
        
        _log(f"Found {len(latest_records)} latest records for alive broods")
        
        # Step 3: Truncate and insert into current table
        conn.execute(text("TRUNCATE TABLE current"))
        _log("Truncated current table")
        
        if latest_records:
            insert_query = text("""
                INSERT INTO current(
                    date, life_stage, mortality, cause_of_death, disease,
                    medium_condition, egg_development, behavior_pre, behavior_post,
                    notes, mother_id, set_label, assigned_person, brooder
                )
                VALUES (
                    :date, :life_stage, :mortality, :cause_of_death, :disease,
                    :medium_condition, :egg_development, :behavior_pre, :behavior_post,
                    :notes, :mother_id, :set_label, :assigned_person, :brooder
                )
            """)
            
            conn.execute(insert_query, [dict(r) for r in latest_records])
            _log(f"Inserted {len(latest_records)} records into current table")
        
        # Step 4: Update meta table
        meta_updates = {
            "current_last_refresh": _now_iso(),
            "current_row_count": str(len(latest_records)),
            "current_alive_broods": str(len(alive_mother_ids)),
        }
        
        for k, v in meta_updates.items():
            conn.execute(text("""
                INSERT INTO meta(k, v) VALUES (:k, :v)
                ON CONFLICT (k) DO UPDATE SET v = EXCLUDED.v
            """), {"k": k, "v": v})
        
        _log("Meta table updated")
    
    _log("ETL done.")


if __name__ == "__main__":
    main()
