# rubber_additive_report_with_pubchem.py (test script)
import os
import re
import sqlite3
import pandas as pd
import query_pubchem as qp

OUT_DIR = "hazard_exports"
TARGETS = [
    "Magnesium Oxide",
    "Magnesium Hydroxide",
    "Calcium Oxide",
    "Calcium Hydroxide",
    "carbon black",
]

# Force carbon black to that exact PubChem URL/CID (no engine changes)
CID_FORCE = {
    "carbon black": 172866199
}

os.makedirs(OUT_DIR, exist_ok=True)

def safe_filename(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_") or "compound"

def resolve_cid(term: str) -> int:
    key = term.strip().lower()
    if key in CID_FORCE:
        return CID_FORCE[key]
    return qp.get_cid_by_name(term)  # uses your existing engine logic

def fetch_core(conn, cid: int) -> dict:
    df = pd.read_sql_query(
        "SELECT cid, name, common_name, formula, molecular_weight, smiles, image_path FROM compounds WHERE cid = ?",
        conn, params=(cid,)
    )
    if df.empty:
        return {"cid": cid, "name": "", "common_name": "", "formula": "", "molecular_weight": "", "smiles": "", "image_path": ""}
    return df.iloc[0].to_dict()

def fetch_cas(conn, cid: int) -> str:
    df = pd.read_sql_query(
        """
        SELECT property_value
        FROM properties
        WHERE cid = ?
          AND lower(property_name) IN (
            'cas', 'cas number', 'cas registry number', 'cas registry no.', 'cas rn', 'casrn'
          )
        LIMIT 1
        """,
        conn, params=(cid,)
    )
    return "" if df.empty else str(df.iloc[0]["property_value"])

def fetch_hazards(conn, cid: int) -> pd.DataFrame:
    df = pd.read_sql_query(
        """
        SELECT category, property_name, property_value
        FROM properties
        WHERE cid = ?
          AND (
                lower(category) = 'hazard'
             OR lower(property_name) LIKE '%hazard%'
             OR lower(property_name) LIKE '%ghs%'
             OR lower(property_name) LIKE '%first aid%'
             OR lower(property_name) LIKE '%pictogram%'
             OR lower(property_name) LIKE '%signal word%'
             OR lower(property_name) LIKE '%h-stat%'
             OR lower(property_name) LIKE '%p-stat%'
          )
        ORDER BY category, property_name
        """,
        conn, params=(cid,)
    )
    if df.empty:
        df = pd.DataFrame([{"category": "Hazard", "property_name": "Hazards", "property_value": ""}])
    return df

def export_one(conn, term: str, cid: int):
    core = fetch_core(conn, cid)
    cas = fetch_cas(conn, cid)
    haz = fetch_hazards(conn, cid)

    # flatten: attach identifiers to each hazard row
    for k, v in core.items():
        haz[k] = v
    haz["cas_no"] = cas
    haz["query_term"] = term

    cols = [
        "query_term", "cid", "cas_no",
        "name", "common_name", "formula", "molecular_weight", "smiles", "image_path",
        "category", "property_name", "property_value"
    ]
    haz = haz[[c for c in cols if c in haz.columns]]

    out_path = os.path.join(OUT_DIR, f"{safe_filename(term)}_{cid}_hazards.csv")
    haz.to_csv(out_path, index=False)
    print(f"[OK] Wrote: {out_path}")

def main():
    # 1) ingest into DB
    for term in TARGETS:
        forced_cid = CID_FORCE.get(term.strip().lower())
        if forced_cid is not None:
            qp.process_compound_name(forced_cid, rebuild_wide=False)
        else:
            qp.process_compound_name(term, rebuild_wide=False)

    qp.rebuild_wide_properties_table()

    # 2) export ALL into one dataframe
    conn = sqlite3.connect(getattr(qp, "DB_PATH", "compounds.db"))

    all_rows = []

    for term in TARGETS:
        cid = resolve_cid(term)

        core = fetch_core(conn, cid)
        cas = fetch_cas(conn, cid)
        haz = fetch_hazards(conn, cid)

        # attach identifiers
        for k, v in core.items():
            haz[k] = v

        haz["cas_no"] = cas
        haz["query_term"] = term

        all_rows.append(haz)

    conn.close()

    # Combine everything
    final_df = pd.concat(all_rows, ignore_index=True)

    cols = [
        "query_term", "cid", "cas_no",
        "name", "common_name", "formula", "molecular_weight",
        "smiles", "image_path",
        "category", "property_name", "property_value"
    ]

    final_df = final_df[[c for c in cols if c in final_df.columns]]

    out_path = os.path.join(OUT_DIR, "rubber_additives_hazards_combined.csv")
    final_df.to_csv(out_path, index=False)

    print(f"[OK] Wrote combined file: {out_path}")

if __name__ == "__main__":
    main()
