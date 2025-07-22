import sqlite3
import pandas as pd

conn = sqlite3.connect("compounds.db")
df = pd.read_sql_query("SELECT * FROM properties", conn)

# Get most common property names
print("\n📌 Top property names:")
print(df["property_name"].value_counts().head(30))

# Get long values (over 300 characters)
long_vals = df[df["property_value"].str.len() > 300]
print(f"\n📄 Long entries (over 300 chars): {len(long_vals)}")

# Preview some long values for 'Uses'
print("\n🧾 Sample long 'Uses' field:")
print(df[df["property_name"] == "Uses"]["property_value"].iloc[0][:500])

# Null-like or redundant entries
print("\n❌ Suspect entries (None/empty):")
print(df[df["property_value"].isin(["None", "", "Not available", "N/A"])])

# After querying a compound like 'sulfuric acid' or 'benzene'

# View raw hazard fields
df = pd.read_sql_query("SELECT * FROM properties WHERE category = 'Hazards'", conn)

print("\n🧯 Hazard fields:")
print(df["property_name"].value_counts())

print("\n📄 Sample values:")
for i in range(min(5, len(df))):
    print(f"\n{df.iloc[i]['property_name']}:")
    print(df.iloc[i]['property_value'])

# View summarized hazard field
summary_df = pd.read_sql_query("""
    SELECT * FROM properties 
    WHERE category = 'Computed' 
      AND property_name = 'Hazards Summary'
""", conn)

print("\n📋 Hazards Summary:")
for i, row in summary_df.iterrows():
    print(f"\n🔹 Compound CID {row['cid']}:\n{row['property_value']}")


conn.close()