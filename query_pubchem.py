import os
import requests
import sqlite3
import json
from bs4 import BeautifulSoup

BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
WEB_URL = "https://pubchem.ncbi.nlm.nih.gov/compound"
DB_PATH = "compounds.db"
IMAGE_DIR = "structure_images"

os.makedirs(IMAGE_DIR, exist_ok=True)

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

def scrape_experimental_properties(cid):
    url = f"{WEB_URL}/{cid}"
    r = requests.get(url)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, 'html.parser')
    prop_blocks = soup.select("section div.section-content div.summary-view div.section-title")
    found = {}

    for block in prop_blocks:
        label = block.text.strip()
        value_el = block.find_next("div")
        if value_el:
            value = value_el.text.strip()
            if any(k in label.lower() for k in ["melting", "boiling", "solubility", "ph", "logp", "density"]):
                found[label] = value
    return found

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

    # Compounds table
    c.execute('''
        CREATE TABLE IF NOT EXISTS compounds (
            cid INTEGER PRIMARY KEY,
            name TEXT,
            formula TEXT,
            molecular_weight REAL,
            smiles TEXT,
            image_path TEXT
        )
    ''')

    # Properties table (grows dynamically)
    c.execute('''
        CREATE TABLE IF NOT EXISTS properties (
            cid INTEGER,
            property_name TEXT,
            property_value TEXT,
            PRIMARY KEY (cid, property_name)
        )
    ''')

    conn.commit()
    return conn

def insert_or_update_compound(conn, props, image_path):
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO compounds 
        (cid, name, formula, molecular_weight, smiles, image_path)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        props.get("CID"),
        props.get("IUPACName"),
        props.get("MolecularFormula"),
        props.get("MolecularWeight"),
        props.get("CanonicalSMILES"),
        image_path
    ))
    conn.commit()

def insert_properties(conn, cid, properties: dict):
    c = conn.cursor()
    for key, value in properties.items():
        c.execute('''
            INSERT OR REPLACE INTO properties
            (cid, property_name, property_value)
            VALUES (?, ?, ?)
        ''', (cid, key, value))
    conn.commit()

def extract_physical_properties(record_json):
    properties = {}
    props = record_json.get("PC_Compounds", [])[0].get("props", [])
    for prop in props:
        label = prop.get("urn", {}).get("label", "")
        name = prop.get("urn", {}).get("name", "")
        value = prop.get("value", {})
        key = f"{label} - {name}" if name else label

        # Read numeric or string value
        val = value.get("sval") or value.get("fval") or value.get("ival")
        if val is not None:
            properties[key.strip()] = str(val)
    return properties

def process_compound_name(name):
    try:
        print(f"🔍 Searching PubChem for: {name}")
        cid = get_cid_by_name(name)
        props = get_properties_by_cid(cid)
        record_json = get_full_record(cid)
        image_path = save_structure_image(cid, name)

        conn = init_db()
        insert_or_update_compound(conn, props, image_path)

        # Extract from JSON
        prop_data = extract_physical_properties(record_json)

        # If none found, fallback to scraping
        if not prop_data:
            print("🧪 No JSON properties found. Scraping fallback...")
            prop_data = scrape_experimental_properties(cid)

        insert_properties(conn, cid, prop_data)
        conn.close()

        print("\n✅ Compound Saved:")
        print(f"CID: {props.get('CID')}")
        print(f"Name: {props.get('IUPACName')}")
        print(f"Formula: {props.get('MolecularFormula')}")
        print(f"MW: {props.get('MolecularWeight')} g/mol")
        print(f"SMILES: {props.get('CanonicalSMILES')}")
        print(f"Image Path: {image_path}")
        print(f"🧪 {len(prop_data)} properties stored.")

    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error: {e}")
    except Exception as e:
        print(f"⚠️ Unexpected Error: {e}")

# CLI
if __name__ == "__main__":
    name = input("Enter compound name: ").strip()
    process_compound_name(name)