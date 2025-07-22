import sqlite3
import pandas as pd
import re
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
import matplotlib.pyplot as plt

# === CONFIG ===
DB_PATH = "compounds.db"
TABLE_NAME = "compound_properties_wide"
TARGET_KEYWORDS = ["Highly Flammable", "Strong Oxidizer"]

# === LOAD DATA ===
conn = sqlite3.connect(DB_PATH)
df = pd.read_sql_query(f"SELECT * FROM {TABLE_NAME}", conn)
conn.close()

# === CLEAN COLUMN NAMES ===
df.columns = [c.strip() for c in df.columns]

# === BINARY TARGET LABEL ===
def label_hazard(hazard_text):
    if not isinstance(hazard_text, str):
        return 0
    for keyword in TARGET_KEYWORDS:
        if re.search(re.escape(keyword), hazard_text, re.IGNORECASE):
            return 1
    return 0

df["target"] = df["Hazards"].apply(label_hazard)

# === DROP ROWS WITHOUT LABEL ===
df = df.dropna(subset=["target"])

# === SELECT NUMERIC FEATURES ===
numeric_df = df.select_dtypes(include=["float64", "int64"]).copy()
feature_cols = [col for col in numeric_df.columns if col != "cid" and col != "target"]

X = numeric_df[feature_cols].fillna(0)
y = df["target"]

# === TRAIN/TEST SPLIT ===
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# === TRAIN RANDOM FOREST ===
clf = RandomForestClassifier(n_estimators=100, random_state=42)
clf.fit(X_train, y_train)

# === EVALUATION ===
y_pred = clf.predict(X_test)
print("Accuracy:", accuracy_score(y_test, y_pred))
print(classification_report(y_test, y_pred))

# === FEATURE IMPORTANCE ===
importances = clf.feature_importances_
feature_importance = pd.Series(importances, index=feature_cols).sort_values(ascending=False)

print("\nTop 10 Important Features:")
print(feature_importance.head(10))

# === OPTIONAL: PLOT FEATURE IMPORTANCE ===
feature_importance.head(10).plot(kind="barh")
plt.gca().invert_yaxis()
plt.title("Top 10 Features Predicting Hazards")
plt.xlabel("Importance")
plt.tight_layout()
plt.show()
