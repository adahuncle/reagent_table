import sqlite3
import pandas as pd

def inspect_table(conn, table_name):
    try:
        df = pd.read_sql_query(f"SELECT * FROM {table_name} LIMIT 50", conn)

        print(f"\n📋 Columns in '{table_name}':")
        print(list(df.columns))

        print(f"\n🔍 Preview of '{table_name}' data:")
        print(df)

    except Exception as e:
        print(f"⚠️ Error reading table '{table_name}':", e)

def inspect_compounds_db(db_path="compounds.db"):
    try:
        conn = sqlite3.connect(db_path)
        inspect_table(conn, "compounds")
        inspect_table(conn, "properties")
        inspect_table(conn, "compound_properties_wide")

    except Exception as e:
        print("⚠️ Database connection error:", e)

    finally:
        conn.close()

if __name__ == "__main__":
    inspect_compounds_db()
