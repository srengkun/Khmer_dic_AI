import os
import sys
import psycopg2
from datasets import load_dataset

# --- Configuration ---
# !!! IMPORTANT !!!
# Paste your Vercel Postgres Connection String here.
# You can find it in your project's storage settings on Vercel.
DATABASE_URL = "postgres://default:xxxxxxxx@xxxx.xxxx.postgres.vercel-storage.com:5432/verceldb"
DATASET_NAME = "seanghay/khmer-dictionary-44k"

def setup_database():
    """
    Downloads the dataset and populates the PostgreSQL database.
    This script should be run ONLY ONCE from your local machine.
    """
    if "xxxxxxxx" in DATABASE_URL:
        print("❌ Error: Please replace 'xxxxxxxx' in the DATABASE_URL with your actual connection string.", file=sys.stderr)
        sys.exit(1)

    print(f"--- Connecting to the database... ---")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
    except Exception as e:
        print(f"❌ Failed to connect to the database: {e}", file=sys.stderr)
        sys.exit(1)

    print("--- Creating tables (if they don't exist)... ---")
    
    # Create dictionary table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dictionary (
            id SERIAL PRIMARY KEY,
            word TEXT NOT NULL,
            pos TEXT,
            definition TEXT
        );
    """)
    
    # Create users table for stats
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            first_name TEXT,
            username TEXT,
            chat_count INTEGER DEFAULT 0,
            last_seen TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()

    # Check if dictionary is already populated
    cursor.execute("SELECT COUNT(*) FROM dictionary")
    if cursor.fetchone()[0] > 0:
        print("ℹ️ The 'dictionary' table is not empty. Skipping population.")
        conn.close()
        return

    print(f"--- Downloading dataset '{DATASET_NAME}'... This may take a while. ---")
    try:
        dataset = load_dataset(DATASET_NAME, split="train")
    except Exception as e:
        print(f"❌ Failed to download dataset: {e}", file=sys.stderr)
        conn.close()
        sys.exit(1)

    print(f"--- Download complete! Preparing to insert {len(dataset)} words... ---")
    
    # Use a set to handle duplicate entries from the dataset
    to_db = list({(row['word'].strip(), row['pos'], row['definition']) for row in dataset if row['word'] and row['word'].strip()})
    
    print(f"--- Inserting {len(to_db)} unique words into the database... ---")
    sql = "INSERT INTO dictionary (word, pos, definition) VALUES (%s, %s, %s)"
    
    try:
        cursor.executemany(sql, to_db)
        conn.commit()
    except Exception as e:
        print(f"❌ Failed to insert data: {e}", file=sys.stderr)
        conn.rollback()
        conn.close()
        sys.exit(1)

    print("--- Creating index for fast searching... ---")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_khmer_word ON dictionary (word);")
    conn.commit()
    conn.close()
    
    print("\n✅ Database has been populated successfully!")

if __name__ == "__main__":
    setup_database()
