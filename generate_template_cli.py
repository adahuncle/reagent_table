import sqlite3
import json
import os

DB_PATH = "compounds.db"
TEMPLATE_DIR = "templates"

# Ensure templates directory exists
os.makedirs(TEMPLATE_DIR, exist_ok=True)

# Load fields from the database
def load_fields():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(compounds)")
    compounds_fields = [row[1] for row in cur.fetchall()]
    cur.execute("PRAGMA table_info(compound_properties_wide)")
    properties_fields = [row[1] for row in cur.fetchall()]
    conn.close()
    return compounds_fields, properties_fields

# Prompt the user to select from fields
def fuzzy_field_prompt(available_fields, prompt):
    while True:
        search = input(f"{prompt} (type partial field name to search): ").strip().lower()
        matches = [f for f in available_fields if search in f.lower()]
        if not matches:
            print("No matches found. Try again.")
            continue
        print("Matches:")
        for i, match in enumerate(matches):
            print(f"  [{i}] {match}")
        idx = input("Enter number of desired field: ").strip()
        if idx.isdigit() and 0 <= int(idx) < len(matches):
            return matches[int(idx)]
        print("Invalid selection. Try again.")

# Build a column definition
def build_column(available_fields):
    column_type = input("Column type [text/image/composite/blank]: ").strip().lower()
    while column_type not in {"text", "image", "composite", "blank"}:
        column_type = input("❌ Invalid. Choose [text/image/composite/blank]: ").strip().lower()

    col_def = {"type": column_type}

    if column_type != "blank":
        header = input("Header name for this column: ").strip()
        col_def["header"] = header

    if column_type == "text":
        source = input("Source [core/properties]: ").strip().lower()
        while source not in {"core", "properties"}:
            source = input("❌ Choose 'core' or 'properties': ").strip().lower()
        col_def["source"] = source
        field = fuzzy_field_prompt(available_fields[source], "Search field")
        col_def["field"] = field

    elif column_type == "image":
        field = fuzzy_field_prompt(available_fields["core"], "Select image path field")
        col_def["field"] = field

    elif column_type == "composite":
        col_def["components"] = []
        while True:
            ctype = input("Add component [text/image/done]: ").strip().lower()
            if ctype == "done":
                break
            elif ctype == "text":
                source = input("Source [core/properties]: ").strip().lower()
                while source not in {"core", "properties"}:
                    source = input("❌ Choose 'core' or 'properties': ").strip().lower()
                field = fuzzy_field_prompt(available_fields[source], "Select text field")
                prefix = input("Prefix (or leave blank): ").strip()
                comp = {"type": "text", "source": source, "field": field}
                if prefix:
                    comp["prefix"] = prefix
                col_def["components"].append(comp)
            elif ctype == "image":
                field = fuzzy_field_prompt(available_fields["core"], "Select image field")
                comp = {"type": "image", "field": field}
                col_def["components"].append(comp)
            else:
                print("❌ Invalid type.")
        text_pos = input("Text position relative to image [top/bottom]: ").strip().lower()
        if text_pos in {"top", "bottom"}:
            col_def["text_position"] = text_pos

    return col_def

# Main function to create a template
def main():
    print("📋 Building new reagent table template...")
    compounds_fields, properties_fields = load_fields()
    available_fields = {"core": compounds_fields, "properties": properties_fields}

    template_name = ""
    while not template_name or template_name.lower() == "default":
        template_name = input("Enter a name for this template (not 'default'): ").strip()
        if template_name.lower() == "default":
            print("❌ 'default' is reserved. Choose another name.")

    num_cols = int(input("How many columns do you want in your template? ").strip())

    template = {"columns": []}
    for i in range(num_cols):
        print(f"\n🧱 Defining column {i+1}/{num_cols}:")
        col = build_column(available_fields)
        template["columns"].append(col)

    output_path = os.path.join(TEMPLATE_DIR, f"{template_name}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(template, f, indent=2)

    print(f"\n✅ Template saved to: {output_path}")

if __name__ == "__main__":
    main()
