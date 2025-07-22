import sqlite3
import pandas as pd

conn = sqlite3.connect("compounds.db")
df = pd.read_sql_query("SELECT * FROM properties", conn)

# Filter long entries over 300 characters
long_df = df[df["property_value"].str.len() > 300]

# 📊 Summary of long entries
print("\n📊 Long Entry Summary by Category and Property:")
print(long_df.groupby(["category", "property_name"]).size().sort_values(ascending=False))

# 🧾 Sample top 5 long entries
print("\n🧾 Sample Long Entries:")
for idx, row in long_df.head(5).iterrows():
    print(f"\n🔸 CID {row['cid']} | {row['category']} → {row['property_name']}")
    print(row['property_value'][:500] + '...')

# 📋 Full grouped breakdown of all long fields
grouped = long_df.groupby(["category", "property_name"]).size().reset_index(name='count')
print("\n📋 All long text fields (>300 chars):")
print(grouped.sort_values(by="count", ascending=False).to_string(index=False))

conn.close()
