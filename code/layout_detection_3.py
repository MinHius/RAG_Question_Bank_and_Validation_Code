"""PyMuPdf for images and texts + Pdfplumber for tables"""
import fitz 
import pdfplumber
import os
from pathlib import Path
from collections import defaultdict
import re


input_file = "C:/Users/Dell/Desktop/TÀI LIỆU ĐÀO TẠO AN TOÀN THÔNG TIN 2025.pdf"
output_path = Path("extracted_3")
table_coords = defaultdict(list)

def is_indexing(line: str) -> bool:
    line = line.strip()
    return bool(re.match(r"^(\d+[\.\)]|[A-Z][\.\)])\s*$|^[•\-]\s*$", line))

def make_merged(merged):
    if merged:
        # join the last merged symbol(s) with this text
        tmp = merged.pop(-1)
        line_text = "".join(tmp) + " " + line_text
    return line_text, merged

def make_small_line(content, small_line):
    content = content + small_line
    return content


def fix_bullet_lists(md_text: str) -> str:
    lines = md_text.splitlines()
    fixed_lines = []
    buffer = []  # hold potential bullet/numbered list
    in_list = False

    def flush_buffer():
        nonlocal fixed_lines, buffer
        if not buffer:
            return

        # check if it's numbered or bullets
        if all(re.match(r"^\d+[\.\)]", l.strip()) for l in buffer):
            # sort by number
            buffer.sort(key=lambda l: int(re.match(r"^(\d+)", l.strip()).group(1)))
        # for • or - bullets, just keep order

        fixed_lines.extend(buffer)
        buffer.clear()

    for line in lines:
        if re.match(r"^(\d+[\.\)]|[•\-])\s+", line):
            buffer.append(line)
            in_list = True
        else:
            if in_list:
                flush_buffer()
                in_list = False
            fixed_lines.append(line)

    # flush last block
    if buffer:
        flush_buffer()

    return "\n".join(fixed_lines)


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
        
        # blocks = sorted(
        #     text_dict["blocks"],
        #     key=lambda b: (b["bbox"][1], b["bbox"][0])  # (y0, x0)
        # )
        
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

            previous_len = 1
            for line in block["lines"]:
                line_text = "".join(span["text"] for span in line["spans"]).strip()
                if not line_text:  # skip empty lines
                    continue
                if re.fullmatch(r"\d+", line_text.strip()) and rect.y1 > page.rect.height * 0.9:
                    continue  # skip footer page number

                
                # print(line_text + " " + str(len(line_text.split())))
                if len(line_text.split()) in range(1,6):
                    if not is_indexing(line_text):
                        if content[-1] != " ":
                            if content[-1] in [".", ";", ":"]:
                                content += "\n\n"
                                content += line_text
                            else:
                                content += " " + line_text
                        # if "." in line_text:
                        #     content += "\n"
                        previous_len = len(line_text.strip())
                    else:
                        merged.append(line_text)
                        bulleted_line = merged.pop(-1)
                        content += "\n" + bulleted_line + " "
                        previous_len = 6
                else:
                    if previous_len < len(line_text.strip()) and previous_len in range(1,6):
                        content += "\n"
                    elif content[-1].isalpha():
                        content += " "
                    content += line_text
                    previous_len = len(line_text.strip())
                    
            
        # Save to Markdown
        file_path = output_path / f"{page_count}" / f"page_{page_count}_text.md"
        file_path.parent.mkdir(parents=True, exist_ok=True)

        content = fix_bullet_lists(content)

        with open(file_path, "w", encoding="utf-8") as md_file:
            md_file.write(content)

        # Append schema refs
        with open(file_path, "a", encoding="utf-8") as md_file:
            md_file.write("\n")
            for tb in table_bboxes:
                md_file.write(f"[Schema]({tb['path'].name})\n")
            
        img_paths = []
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
            img_paths.append(img_path)
                
        with open(file_path, "a", encoding="utf-8") as md_file:
            md_file.write("\n")
            for path in img_paths:
                md_file.write(f"[Schema]({path.name})\n")



if __name__ == "__main__":
    table()
    text_and_image()


