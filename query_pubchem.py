import os
import requests
import sqlite3
import pandas as pd
import time
import re
import html

BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
VIEW_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound"
DB_PATH = "compounds.db"
IMAGE_DIR = "structure_images"

os.makedirs(IMAGE_DIR, exist_ok=True)

def summarize_text(text, max_lines=5):
    if not isinstance(text, str):
        return text
    parts = [p.strip(" ;,") for p in text.split(";") if p.strip()]
    return "; ".join(parts[:max_lines]) + ("..." if len(parts) > max_lines else "")

def normalize_property(prop_name, value):
    prop_name = str(prop_name)
    value = html.unescape(value)
    value = re.sub(r"[^\x00-\x7F°±µ]+", " ", value)
    value = value.replace("•", "-")

    if not isinstance(value, str):
        return value

    value = value.strip()
    lower_name = prop_name.lower()

    # 🔍 Remove bracketed references like [ChemIDplus]
    value = re.sub(r"\[[^\]]*?\]", "", value)

    # 🧼 Clean None-like values
    if value.lower() in {"none", "not available", "n/a", "null", "not applicable"}:
        return ""

    # 🔢 Extract numeric if applicable
    # if any(key in lower_name for key in ["mass", "weight", "boiling", "melting", "logp", "density", "ph"]):
        match = re.search(r"[-+]?[0-9]*\.?[0-9]+", value)
        if match:
            return match.group(0)

    # ✂ Summarize long text
    if any(key in lower_name for key in ["use", "hazard", "method", "impurities", "decomposition", "purpose", "manufacturing"]):
        if len(value.split()) > 40:
            return summarize_text(value, max_lines=5)

    return value.strip()

def extract_hazard_traits(text):
    match = re.search(r"Hazard Traits\s*-\s*(.+?)(;|$)", text)
    return match.group(1) if match else ""

def extract_hazard_and_first_aid(hazards_dict):
    """
    Extracts raw 'Hazard Traits' and 'First Aid Measures' as clean, semicolon-separated strings.
    Returns: (hazards_cleaned, first_aid_cleaned)
    """
    reg_info = hazards_dict.get("Regulatory Information", "")
    first_aid = hazards_dict.get("First Aid Measures", "")

    # Extract Hazard Traits
    hazard_traits = ""
    match = re.search(
        r"Hazard Traits\s*-\s*(.+?)(?:\s*(Authoritative List|Report|Status|Chemical|Restricted substance|List II Chemical|https?://|$))",
        reg_info,
        re.IGNORECASE | re.DOTALL
    )
    if match:
        hazard_traits = match.group(1).strip(" ;.\n")

    # Normalize newlines and semicolons in both fields
    def clean_multiline(text):
        if not text:
            return ""
        lines = [line.strip(" ;.\n") for line in text.splitlines() if line.strip()]
        return "; ".join(lines)

    return clean_multiline(hazard_traits), clean_multiline(first_aid)


def get_cid_by_name(name):
    url = f"{BASE_URL}/compound/name/{name}/cids/JSON"
    r = requests.get(url)
    r.raise_for_status()
    return r.json()["IdentifierList"]["CID"][0]

def get_properties_by_cid(cid):
    url = f"{BASE_URL}/compound/cid/{cid}/property/IUPACName,MolecularFormula,MolecularWeight,CanonicalSMILES/JSON"
    r = requests.get(url)
    r.raise_for_status()
    return r.json()["PropertyTable"]["Properties"][0]

def get_full_record(cid):
    url = f"{BASE_URL}/compound/cid/{cid}/record/JSON"
    r = requests.get(url)
    r.raise_for_status()
    return r.json()

def get_pug_view_data(cid):
    url = f"{VIEW_URL}/{cid}/JSON"
    r = requests.get(url)
    r.raise_for_status()
    return r.json()

def extract_common_name(view_data):
    try:
        sections = view_data.get("Record", {}).get("Section", [])
        for sec in sections:
            if sec.get("TOCHeading") == "Names and Identifiers":
                for sub in sec.get("Section", []):
                    if sub.get("TOCHeading") == "Synonyms":
                        for info in sub.get("Information", []):
                            synonyms = info.get("Value", {}).get("StringWithMarkup", [])
                            names = [item.get("String") for item in synonyms if item.get("String")]
                            if not names:
                                continue

                            # Prefer simple, short, ASCII, capitalized or lowercase names with no numbers
                            clean_names = [n.strip() for n in names if n.isascii() and not any(c.isdigit() for c in n)]
                            if clean_names:
                                # Return the shortest alphabetic name
                                return sorted(clean_names, key=lambda s: (len(s), s.lower()))[0]

                            return names[0].strip()  # fallback: just return the first synonym
    except Exception as e:
        print(f"⚠️ Common name extraction failed: {e}")
    return None

def extract_experimental_properties(view_data):
    result = {}
    sections = view_data.get("Record", {}).get("Section", [])
    def recurse_sections(sections):
        for sec in sections:
            heading = sec.get("TOCHeading", "")
            if heading == "Experimental Properties":
                for sub in sec.get("Section", []):
                    prop_name = sub.get("TOCHeading", "")
                    for info in sub.get("Information", []):
                        value = info.get("Value", {}).get("StringWithMarkup", [{}])[0].get("String")
                        if value:
                            result[prop_name] = value
            elif "Section" in sec:
                recurse_sections(sec["Section"])
    recurse_sections(sections)
    return result

def extract_hazard_properties(view_data):
    result = {}
    sections = view_data.get("Record", {}).get("Section", [])

    def recurse_sections(sections):
        for sec in sections:
            heading = sec.get("TOCHeading", "")
            if heading == "Safety and Hazards":
                for sub in sec.get("Section", []):
                    subheading = sub.get("TOCHeading", "")
                    values = []
                    for info in sub.get("Information", []):
                        value_data = info.get("Value", {}).get("StringWithMarkup", [])
                        for item in value_data:
                            string = item.get("String")
                            if string:
                                values.append(string)
                    if values:
                        result[subheading] = "; ".join(values)
            elif "Section" in sec:
                recurse_sections(sec["Section"])

    recurse_sections(sections)
    return result

def extract_use_properties(view_data):
    result = {}
    sections = view_data.get("Record", {}).get("Section", [])

    def recurse_sections(sections):
        for sec in sections:
            heading = sec.get("TOCHeading", "")
            if heading == "Use and Manufacturing":
                for sub in sec.get("Section", []):
                    subheading = sub.get("TOCHeading", "")
                    values = []
                    for info in sub.get("Information", []):
                        value_data = info.get("Value", {}).get("StringWithMarkup", [])
                        for item in value_data:
                            string = item.get("String")
                            if string:
                                values.append(string)
                    if values:
                        result[subheading] = "; ".join(values)
            elif "Section" in sec:
                recurse_sections(sec["Section"])

    recurse_sections(sections)
    return result

def save_structure_image(cid, compound_name):
    image_url = f"{BASE_URL}/compound/cid/{cid}/PNG"
    r = requests.get(image_url)
    r.raise_for_status()
    filename = f"{compound_name.replace(' ', '_')}_{cid}.png"
    path = os.path.join(IMAGE_DIR, filename)
    with open(path, "wb") as f:
        f.write(r.content)
    return path

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS compounds (
            cid INTEGER PRIMARY KEY,
            name TEXT,
            common_name TEXT,
            formula TEXT,
            molecular_weight REAL,
            smiles TEXT,
            image_path TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS properties (
            cid INTEGER,
            category TEXT,
            property_name TEXT,
            property_value TEXT,
            PRIMARY KEY (cid, category, property_name)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS compound_properties_wide (
            cid INTEGER PRIMARY KEY
        )
    ''')

    conn.commit()
    return conn

def insert_or_update_compound(conn, props, image_path, common_name):
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO compounds 
        (cid, name, common_name, formula, molecular_weight, smiles, image_path)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        props.get("CID"),
        props.get("IUPACName"),
        common_name,
        props.get("MolecularFormula"),
        props.get("MolecularWeight"),
        props.get("CanonicalSMILES"),
        image_path
    ))
    conn.commit()

def insert_properties(conn, cid, category, properties: dict):
    c = conn.cursor()
    for key, value in properties.items():
        norm_key = str(key).strip()
        norm_value = normalize_property(norm_key, str(value).strip())

        # ⚠️ Only keep long text fields from specific subfields
        if category == "Uses" and norm_key not in {"Uses", "Impurities"}:
            continue

        c.execute('''
            INSERT OR REPLACE INTO properties
            (cid, category, property_name, property_value)
            VALUES (?, ?, ?, ?)
        ''', (cid, category, norm_key, norm_value))
    conn.commit()

def extract_computed_properties(record_json):
    properties = {}
    props = record_json.get("PC_Compounds", [])[0].get("props", [])
    for prop in props:
        label = prop.get("urn", {}).get("label", "")
        name = prop.get("urn", {}).get("name", "")
        value = prop.get("value", {})
        key = f"{label} - {name}" if name else label
        val = value.get("sval") or value.get("fval") or value.get("ival")
        if val is not None:
            properties[key.strip()] = val
    return properties

def build_wide_properties_table(conn):
    df = pd.read_sql_query("SELECT * FROM properties", conn)
    if df.empty:
        print("⚠️ No properties data to pivot.")
        return

    df_wide = df.pivot_table(index="cid", columns="property_name", values="property_value", aggfunc='first')
    df_wide.reset_index(inplace=True)
    df_wide.to_sql("compound_properties_wide", conn, if_exists="replace", index=False)
    print("📊 Wide-format properties table generated: compound_properties_wide")

def process_compound_name(name):
    try:
        print(f"🔍 Searching PubChem for: {name}")
        cid = get_cid_by_name(name)
        props = get_properties_by_cid(cid)
        record_json = get_full_record(cid)
        view_json = get_pug_view_data(cid)
        image_path = save_structure_image(cid, name)
        common_name = extract_common_name(view_json)
        print(f"📛 Common Name selected: {common_name}")

        conn = init_db()
        insert_or_update_compound(conn, props, image_path, common_name)

        computed = extract_computed_properties(record_json)
        insert_properties(conn, cid, "Computed", computed)

        uses = extract_use_properties(view_json)
        if uses:
            insert_properties(conn, cid, "Uses", uses)
        else:
            print("⚠️ No use/manufacturing data found via PUG-View.")

        experimental = extract_experimental_properties(view_json)
        hazards = extract_hazard_properties(view_json)

        if experimental:
            insert_properties(conn, cid, "Experimental", experimental)
        else:
            print("⚠️ No experimental data found via PUG-View.")

        if hazards:
            hazard_traits, first_aid = extract_hazard_and_first_aid(hazards)

            if hazard_traits:
                insert_properties(conn, cid, "Hazard", {"Hazards": hazard_traits})

            if first_aid:
                insert_properties(conn, cid, "Hazard", {"First Aid Measures": first_aid})


        build_wide_properties_table(conn)
        conn.close()

        print("\n✅ Compound Saved:")
        print(f"CID: {props.get('CID')}")
        print(f"Name: {props.get('IUPACName')}")
        print(f"Formula: {props.get('MolecularFormula')}")
        print(f"MW: {props.get('MolecularWeight')} g/mol")
        print(f"SMILES: {props.get('CanonicalSMILES')}")
        print(f"Image Path: {image_path}")
        print(f"🧪 {len(computed) + len(experimental)} properties stored.")

    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error: {e}")
    except Exception as e:
        print(f"⚠️ Unexpected Error: {e}")

if __name__ == "__main__":
    input_str = input("Enter compound name(s), comma-separated: ").strip()
    names = [name.strip() for name in input_str.split(',') if name.strip()]

    for name in names:
        print("\n" + "="*50)
        process_compound_name(name)
        time.sleep(1)
