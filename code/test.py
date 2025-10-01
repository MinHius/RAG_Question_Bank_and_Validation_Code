"""PyMuPdf for images and texts + Pdfplumber for tables"""
import math
import fitz 
import pdfplumber
import os
from pathlib import Path
from collections import defaultdict
import re
import time
from validation import validate_parser, extract_table

input_file = "C:/Users/Dell/Desktop/TÀI LIỆU ĐÀO TẠO AN TOÀN THÔNG TIN 2025.pdf"
output_path = Path("extracted_test")
table_coords = defaultdict(list)

def is_indexing(line: str) -> bool:
    return bool(re.match(
    r"""^(
        [\u2022\u2023\u25E6\u2043\u2219\-\+\*•●○■□◆▶►]   # common bullet symbols
        |
        \d+[\.\)]                                       # 1. or 1)
        |
        [A-Z][\.\)\-]                                   # A. or A)
    )(\s+.*)?$""", 
    line.strip(), re.VERBOSE))



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
                file_path = output_path / f"{page_number}" / "table_img" / file_name
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
    runtime = []
    doc = fitz.open(input_file)
    for page_count, page in enumerate(doc, start=1):
        table_extracted = False
        start = time.time()
        text_dict = page.get_text("dict")
        
        content = f"# Page {page_count}\n\n"
        table_bboxes = table_coords.get(page_count, [])

        previous_type = ""
        for block in text_dict["blocks"]:
            if block["type"] != 0:  # only text blocks
                continue
            
            rect = fitz.Rect(*block["bbox"])

            # skip if block overlaps any table
            if any(rect.intersects(fitz.Rect(*tb["coords"])) for tb in table_bboxes):
                if table_extracted == False:
                    folder_path = output_path / f"{page_count}" / "table_img"
                    content += extract_table(folder_path) + "\n\n"
                    table_extracted = True
                continue

            # collect text line by line
            merged = []

            for line in block["lines"]:
                line_text = "".join(span["text"] for span in line["spans"]).strip()
                if not line_text:  # skip empty lines
                    continue
                if re.fullmatch(r"\d+", line_text.strip()) and rect.y1 > page.rect.height * 0.9:
                    continue  # skip footer page number

                
                if len(line_text.split()) in range(1,7):
                    if not is_indexing(line_text):
                        """Short lines, not bullets"""
                        
                        # Current content is at end of sentences
                        if content[-1] != " " and content[-1] in [".", ";", ":"]:
                            content += "\n"
                            
                        # Append short line
                        content += " " + line_text + " "
                        
                        # Short lines having periods
                        if line_text[-1] == ".":
                            content += "\n"
                        previous_type = "short text"
                    else:
                        # Short lines - bullets
                        content += "\n" + line_text + " "
                        previous_type = "bullet"
                else:
                    if previous_type in ["short text"]:
                        content += "\n"
                        
                    # Long line with period
                    if "." == line_text[-1] and len(line_text.split()) > 1:
                        content += line_text + "\n"
                    # Long line - continuous
                    elif content[-1].isalpha() or content[-1] == " ":
                        content += " " + line_text
                    else: 
                        content += " " + line_text + " "
                    previous_type = "long text"
                    
            
        # Save to Markdown
        file_path = output_path / f"{page_count}" / f"page_{page_count}_text.md"
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Sort numeric list
        content = fix_bullet_lists(content)
        
        # LLM re-formatting
        content = validate_parser(content, page_count)
        
        # Write text content
        with open(file_path, "w", encoding="utf-8") as md_file:
            md_file.write(content)

        # Append table path
        with open(file_path, "a", encoding="utf-8") as md_file:
            md_file.write("\n")
            for tb in table_bboxes:
                md_file.write(f"[Schema]({tb['path'].name})\n")
            
        # Extract images
        img_paths = []
        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            pix = fitz.Pixmap(doc, xref)
            img_path = output_path / f"{page_count}" / f"page_{page_count}_img_{img_index}.png"
            img_path.parent.mkdir(parents=True, exist_ok=True)
            if pix.n < 5:  # RGB or grayscale
                pix.save(img_path)
            else:
                pix = fitz.Pixmap(fitz.csRGB, pix)
                pix.save(img_path)
            img_paths.append(img_path)
                
        # Append image path
        with open(file_path, "a", encoding="utf-8") as md_file:
            md_file.write("\n")
            for path in img_paths:
                md_file.write(f"[Schema]({path.name})\n")

        end = time.time()
        runtime.append(end - start)
        
    print(f"Max: {max(runtime)}")
    print(f"Min: {min(runtime)}")
    print(f"Total: {sum(runtime)}")
    print(f"Avg: {sum(runtime) / len(runtime)}")


if __name__ == "__main__":
    table()
    os.makedirs("test_val_test", exist_ok=True)
    text_and_image()


