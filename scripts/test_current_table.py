"""
Test script to verify the current table logic works correctly.
Run this locally before deploying to production.
"""
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DB_URL = os.getenv("DATABASE_URL")

def test_current_table():
    """Test the current table creation and population."""
    print("=" * 60)
    print("Testing current table logic")
    print("=" * 60)
    
    if not DB_URL:
        print("❌ ERROR: DATABASE_URL not found in environment")
        return
    
    engine = create_engine(DB_URL, pool_pre_ping=True)
    
    with engine.connect() as conn:
        # Check broods table
        print("\n1. Checking broods table...")
        broods_count = conn.execute(text("SELECT COUNT(*) FROM broods")).scalar()
        print(f"   Total broods: {broods_count}")
        
        # Check alive broods
        print("\n2. Checking alive broods...")
        alive_query = text("""
            SELECT COUNT(*) 
            FROM broods 
            WHERE (death_date IS NULL OR death_date = '' OR TRIM(death_date) = '')
              AND (status IS NULL OR status = '' 
                   OR LOWER(TRIM(status)) NOT IN ('dead', 'deceased', 'died'))
        """)
        alive_count = conn.execute(alive_query).scalar()
        print(f"   Alive broods: {alive_count}")
        
        # Show sample alive broods
        print("\n3. Sample alive broods:")
        sample_alive = conn.execute(text("""
            SELECT mother_id, set_label, birth_date, death_date, status
            FROM broods 
            WHERE (death_date IS NULL OR death_date = '' OR TRIM(death_date) = '')
              AND (status IS NULL OR status = '' 
                   OR LOWER(TRIM(status)) NOT IN ('dead', 'deceased', 'died'))
            LIMIT 5
        """)).fetchall()
        
        for row in sample_alive:
            print(f"   {row[0]:<20} Set: {row[1]:<5} Birth: {row[2]:<12} Death: {row[3] or 'None':<12} Status: {row[4] or 'None'}")
        
        # Check records table
        print("\n4. Checking records table...")
        records_count = conn.execute(text("SELECT COUNT(*) FROM records")).scalar()
        print(f"   Total records: {records_count}")
        
        # Check if current table exists
        print("\n5. Checking current table...")
        table_exists = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'current'
            )
        """)).scalar()
        
        if table_exists:
            current_count = conn.execute(text("SELECT COUNT(*) FROM current")).scalar()
            print(f"   ✅ Current table exists with {current_count} records")
            
            # Show sample from current table
            print("\n6. Sample records from current table:")
            sample_current = conn.execute(text("""
                SELECT mother_id, date, life_stage, mortality, set_label
                FROM current
                LIMIT 5
            """)).fetchall()
            
            for row in sample_current:
                print(f"   {row[0]:<20} Date: {row[1]:<12} Stage: {row[2]:<15} Mortality: {row[3]:<5} Set: {row[4]}")
        else:
            print("   ⚠️  Current table does not exist yet (will be created on first ETL run)")
        
        print("\n" + "=" * 60)
        print("Test complete!")
        print("=" * 60)


if __name__ == "__main__":
    test_current_table()
