"""PyMuPdf for images and texts + Pdfplumber for tables"""
import fitz 
import pdfplumber
import os
from pathlib import Path
from collections import defaultdict


input_file = "C:/Users/Dell/Desktop/TÀI LIỆU ĐÀO TẠO AN TOÀN THÔNG TIN 2025.pdf"
output_path = Path("extracted_2")
table_coords = defaultdict(list)


def table():
    os.makedirs(output_path, exist_ok=True)

    with pdfplumber.open(input_file) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            tables = page.find_tables()
            for table_index, table in enumerate(tables, start=1):
                file_name = f"page_{page_number}_table_{table_index}.png"
                file_path = output_path / f"{page_number}" / file_name
                file_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Clip bbox to page bounds
                x0, y0, x1, y1 = table.bbox
                table_coords[page_number].append({
                    "coords": [x0, y0, x1, y1],
                    "path": file_path
                })
                px0, py0, px1, py1 = page.bbox

                clipped_bbox = (
                    max(x0, px0),
                    max(y0, py0),
                    min(x1, px1),
                    min(y1, py1)
                )

                # Crop page to table bbox
                cropped_page = page.within_bbox(clipped_bbox)
                table_img = cropped_page.to_image(resolution=150)
                table_img.save(file_path, format="PNG")

                print(f"Saved Page {page_number}, Table {table_index} → {file_path}")
                
                
def text_and_image():
    doc = fitz.open(input_file)
    for page_count, page in enumerate(doc, start=1):
        # Extract dict (structured)
        text_dict = page.get_text("dict")
        content = f"# Page {page_count}\n\n"

        table_bboxes = table_coords.get(page_count, [])

        for block in text_dict["blocks"]:
            if block["type"] != 0:  # only text blocks
                continue
            
            rect = fitz.Rect(*block["bbox"])

            # skip if block overlaps any table
            if any(rect.intersects(fitz.Rect(*tb["coords"])) for tb in table_bboxes):
                continue

            # collect text line by line
            merged = []
            for line in block["lines"]:
                line_text = "".join(span["text"] for span in line["spans"]).strip()

                if not line_text:  # skip empty lines
                    continue

                # if all chars are non-alpha, mark it for merging
                if all(not ch.isalpha() for ch in line_text):
                    merged.append(line_text)
                else:
                    if merged:
                        # join the last merged symbol(s) with this text
                        line_text = "".join(merged) + " " + line_text
                        merged.clear()
                    content += line_text + "\n"
            
        # Save to Markdown
        file_path = output_path / f"{page_count}" / f"page_{page_count}_text.md"
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as md_file:
            md_file.write(content)

        # Append schema refs
        with open(file_path, "a", encoding="utf-8") as md_file:
            for tb in table_bboxes:
                md_file.write(f"[Schema]({tb['path'].name})\n")
            
        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            pix = fitz.Pixmap(doc, xref)
            img_path = output_path / f"{page_count}" / f"page_{page_count}_img_{img_index}.png"
            img_path.parent.mkdir(parents=True, exist_ok=True)
            if pix.n < 5:  # RGB or grayscale
                pix.save(img_path)
            else:  # CMYK
                pix = fitz.Pixmap(fitz.csRGB, pix)
                pix.save(img_path)
                
            with open(file_path, "a", encoding="utf-8") as md_file:
                md_file.write(f"[Schema]({img_path.name})\n")



if __name__ == "__main__":
    table()
    text_and_image()
