import os, sys, sqlite3, pandas as pd

# Default database path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = os.path.join(BASE_DIR, "data", "database.db")

# Allow override from command line
db_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB
mother = sys.argv[2] if len(sys.argv) > 2 else None

# Expand relative path to absolute
db_path = os.path.abspath(db_path)

print(f"DB: {db_path}")

if not os.path.exists(db_path):
    print(f"❌ Database file not found at {db_path}")
    sys.exit(1)

# Connect to DB
con = sqlite3.connect(db_path)

def q(sql):
    try:
        return pd.read_sql(sql, con)
    except Exception as e:
        print("Query error:", e)

print("\nTables:")
print(q("SELECT name FROM sqlite_master WHERE type='table'"))

print("\nRow count in mothers:")
print(q("SELECT COUNT(*) as n FROM mothers"))

print("\nSample rows from mothers:")
print(q("SELECT mother_id,set_label,assigned_person,status FROM mothers LIMIT 10"))

print("\nCounts by assignee:")
print(q("SELECT set_label,assigned_person,COUNT(*) AS n "
       "FROM mothers GROUP BY set_label,assigned_person ORDER BY set_label,assigned_person"))

if mother:
    print(f"\nChildren of {mother}:")
    print(q(f"SELECT mother_id FROM mothers "
            f"WHERE origin_mother_id='{mother}' ORDER BY mother_id"))

con.close()
