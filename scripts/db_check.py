import os, sys
import pandas as pd
from sqlalchemy import create_engine, text

DB_URL = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("DATABASE_URL")
mother = sys.argv[2] if len(sys.argv) > 2 else None
if not DB_URL:
    print("❌ DATABASE_URL not provided"); sys.exit(1)

eng = create_engine(DB_URL, pool_pre_ping=True)

def q(sql, **params):
    with eng.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)

print("\nTables:")
print(q("""SELECT table_name FROM information_schema.tables
          WHERE table_schema='public' ORDER BY table_name"""))

print("\nRow count in mothers:")
print(q("SELECT COUNT(*) as n FROM mothers"))

print("\nSample rows from mothers:")
print(q("SELECT mother_id,set_label,assigned_person,status FROM mothers LIMIT 10"))

print("\nCounts by assignee:")
print(q("""SELECT set_label,assigned_person,COUNT(*) AS n
          FROM mothers GROUP BY set_label,assigned_person
          ORDER BY set_label,assigned_person"""))

if mother:
    print(f"\nChildren of {mother}:")
    print(q("""SELECT mother_id FROM mothers
              WHERE origin_mother_id=:m ORDER BY mother_id""", m=mother))
