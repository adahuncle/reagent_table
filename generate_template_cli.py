import sqlite3
import json
import os

DB_PATH = "compounds.db"
TEMPLATE_DIR = "templates"
os.makedirs(TEMPLATE_DIR, exist_ok=True)

def load_fields():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(compounds)")
    compounds_fields = [row[1] for row in cur.fetchall()]
    cur.execute("PRAGMA table_info(compound_properties_wide)")
    properties_fields = [row[1] for row in cur.fetchall()]
    conn.close()
    return {"core": compounds_fields, "properties": properties_fields}

def fuzzy_field_prompt(available_fields, prompt):
    while True:
        search = input(f"{prompt} (type partial field name to search): ").strip().lower()
        matches = [f for f in available_fields if search in f.lower()]
        if not matches:
            print("❌ No matches found. Try again.")
            continue
        for i, match in enumerate(matches[:20]):
            print(f"  [{i}] {match}")
        idx = input("Enter number of desired field: ").strip()
        if idx.isdigit() and 0 <= int(idx) < len(matches[:20]):
            return matches[int(idx)]
        print("❌ Invalid selection. Try again.")

def build_column(available_fields):
    while True:
        col_type = input("Column type [composite/blank]: ").strip().lower()
        if col_type in {"text", "image", "composite", "blank"}:
            break
        print("❌ Invalid. Choose from [text/image/composite/blank].")

    col_def = {"type": col_type}
    if col_type != "blank":
        col_def["header"] = input("Header name for this column: ").strip()

    if col_type == "text":
        source = input("Source [core/properties]: ").strip().lower()
        while source not in {"core", "properties"}:
            source = input("❌ Choose 'core' or 'properties': ").strip().lower()
        col_def["source"] = source
        col_def["field"] = fuzzy_field_prompt(available_fields[source], "Select text field")

    elif col_type == "image":
        col_def["field"] = fuzzy_field_prompt(available_fields["core"], "Select image path field")

    elif col_type == "composite":
        col_def["components"] = []
        while True:
            ctype = input("Add component [text/image/done]: ").strip().lower()
            if ctype == "done":
                if not col_def["components"]:
                    print("❌ At least one component is required.")
                    continue
                break
            elif ctype == "text":
                source = input("Source [core/properties]: ").strip().lower()
                while source not in {"core", "properties"}:
                    source = input("❌ Choose 'core' or 'properties': ").strip().lower()
                field = fuzzy_field_prompt(available_fields[source], "Select text field")
                prefix = input("Optional prefix: ").strip()
                comp = {"type": "text", "source": source, "field": field}
                if prefix:
                    comp["prefix"] = prefix
                col_def["components"].append(comp)
            elif ctype == "image":
                field = fuzzy_field_prompt(available_fields["core"], "Select image field")
                col_def["components"].append({"type": "image", "field": field})
            else:
                print("❌ Invalid component type.")

        while True:
            pos = input("Text position relative to image [top/bottom]: ").strip().lower()
            if pos in {"top", "bottom"}:
                col_def["text_position"] = pos
                break
            print("❌ Choose either 'top' or 'bottom'.")

    return col_def

def main():
    print("📋 Build a new reagent table template")
    available_fields = load_fields()

    while True:
        template_name = input("Enter template name (not 'default'): ").strip()
        if template_name and template_name.lower() != "default":
            break
        print("❌ Invalid name. Please choose another.")

    while True:
        try:
            num_cols = int(input("How many columns? ").strip())
            if num_cols > 0:
                break
        except ValueError:
            pass
        print("❌ Please enter a valid positive number.")

    template = {"columns": []}
    for i in range(num_cols):
        print(f"\n🧱 Column {i+1}/{num_cols}")
        template["columns"].append(build_column(available_fields))

    path = os.path.join(TEMPLATE_DIR, f"{template_name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(template, f, indent=2)

    print(f"\n✅ Template saved: {path}")

if __name__ == "__main__":
    main()
