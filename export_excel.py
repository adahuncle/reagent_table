import pandas as pd
import sqlite3
import json
import os
from openpyxl import Workbook
from openpyxl.drawing.image import Image as ExcelImage
from openpyxl.utils import get_column_letter
from openpyxl.styles import Alignment
from PIL import Image as PILImage, ImageDraw, ImageFont

DB_PATH = "compounds.db"
EXCEL_PATH = "compound_report.xlsx"
TEMPLATE_PATH = "templates/default.json"

def load_template(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def make_composite_image(image_path, text_lines, text_position="bottom", font_size=14):
    base_img = PILImage.open(image_path).convert("RGBA")
    font = ImageFont.truetype("arial.ttf", font_size)
    spacing = 5

    # Calculate total text height
    draw = ImageDraw.Draw(base_img)
    text_height = sum([draw.textbbox((0,0), line, font=font)[3] for line in text_lines]) + spacing * (len(text_lines) - 1)

    # Create new canvas
    new_height = base_img.height + text_height + 10
    new_img = PILImage.new("RGBA", (base_img.width, new_height), "white")

    # Draw image and text
    if text_position == "top":
        y_offset = text_height + 5
        new_img.paste(base_img, (0, y_offset))
        y_text = 5
    else:
        new_img.paste(base_img, (0, 0))
        y_text = base_img.height + 5

    draw = ImageDraw.Draw(new_img)
    for line in text_lines:
        draw.text((5, y_text), line, font=font, fill="black")
        y_text += font_size + spacing

    return new_img


def generate_excel_from_template(template_path=TEMPLATE_PATH):
    template = load_template(template_path)

    # Load database tables
    conn = sqlite3.connect(DB_PATH)
    df_core = pd.read_sql_query("SELECT * FROM compounds", conn)
    df_props = pd.read_sql_query("SELECT * FROM compound_properties_wide", conn)
    conn.close()

    # Merge into one row-wise DataFrame
    merged = df_core.merge(df_props, on="cid", how="left")

    # Start Excel workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Reagent Table"

    # Write headers
    headers = [col["header"] for col in template["columns"]]
    ws.append(headers)

    # Process each row
    for index, row in merged.iterrows():
        excel_row = []
        for col in template["columns"]:
            if col.get("type") == "composite":
                content = []
                for comp in col["components"]:
                    if comp["type"] == "text":
                        value = row.get(comp["field"], "")
                        if pd.notna(value):
                            prefix = comp.get("prefix", "")
                            content.append(f"{prefix}{value}")
                excel_row.append("\n".join(content))
            elif col.get("type") == "image":
                excel_row.append("")  # Placeholder for image
            else:
                source = col.get("source")
                field = col.get("field")
                value = row.get(field, "")
                excel_row.append(value)
        ws.append(excel_row)

    # Embed composite images into composite fields
    for i, row in merged.iterrows():
        for j, col in enumerate(template["columns"]):
            if col.get("type") == "composite":
                # Gather text components for this composite column
                text_lines = []
                image_path = None
                for comp in col["components"]:
                    if comp["type"] == "text":
                        value = row.get(comp["field"], "")
                        if pd.notna(value):
                            prefix = comp.get("prefix", "")
                            text_lines.append(f"{prefix}{value}")
                    elif comp["type"] == "image":
                        image_path = row.get(comp["field"])

                # Only make composite image if we have a valid image
                if image_path and os.path.exists(image_path):
                    composite_img = make_composite_image(image_path, text_lines, text_position="bottom")
                    # Save composite to temp file
                    base, ext = os.path.splitext(image_path)
                    composite_path = f"{base}_composite.png"
                    composite_img.save(composite_path)

                    img = ExcelImage(composite_path)
                    cell = ws.cell(row=i + 2, column=j + 1)
                    img.anchor = cell.coordinate
                    ws.add_image(img)

                # Adjust cell dimensions slightly larger for better fit
                ws.row_dimensions[i + 2].height = max(ws.row_dimensions[i + 2].height or 0, img.height * 0.85)  # previously 0.75
                col_letter = get_column_letter(j + 1)
                ws.column_dimensions[col_letter].width = max(ws.column_dimensions[col_letter].width or 10, img.width / 5.5)  # previously /6



    # Adjust column widths and alignments
    for j, col in enumerate(template["columns"]):
        col_letter = get_column_letter(j + 1)
        max_length = max((len(str(ws.cell(row=i, column=j + 1).value or "")) for i in range(1, ws.max_row + 1)), default=10)
        ws.column_dimensions[col_letter].width = max(ws.column_dimensions[col_letter].width or 10, max_length + 2)
        for i in range(2, ws.max_row + 1):
            cell = ws.cell(row=i, column=j + 1)
            cell.alignment = Alignment(wrap_text=True, vertical="center")

    # Save file
    wb.save(EXCEL_PATH)
    print(f"✅ Excel generated using template: {template_path}")

if __name__ == "__main__":
    generate_excel_from_template()
