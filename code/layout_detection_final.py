"""PyMuPdf for images and texts + Pdfplumber for tables"""
import math
import fitz 
import pdfplumber
import os
from pathlib import Path
from collections import defaultdict
import re
from validation import validate_parser, extract_page
from config import INPUT_PDF_PATH, OUTPUT_DIR_PATH, PDF_RESOLUTION, MIN_AREA_RATIO



def is_bullet(line: str) -> bool:
    return bool(re.match(
    r"""^(
        [\u2022\u2023\u25E6\u2043\u2219\-\+\*•●○■□◆▶►]   # common bullet symbols
        |
        \d+[\.\)]                                       # 1. or 1)
        |
        [A-Z][\.\)\-]                                   # A. or A)
    )(\s+.*)?$""", 
    line.strip(), re.VERBOSE))

def fix_bullet_list(md_text: str) -> str:
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



def append_short_line(content: str, line_text: str, previous_type: str):
    """ Concatenate short lines in to one complete sentence """
    
    last_char = content[-1] if content else ""
    
    # Current content is at end of sentences
    if last_char in [".", ";", ":"]:
        content += "\n"

    # Append short line
    content += " " + line_text + " "

    # Short line having periods
    if line_text.endswith("."):
        content += "\n"

    # Update for retracing
    previous_type = "short text"
    
    return content, previous_type

def append_long_line(content, line_text, line_length, previous_type):
    """Concatenate long lines into the current page's text content"""
    
    last_char = content[-1] if content else ""
    
    # Long lines after short line 
    # -> End of choppy sentences
    if previous_type == "short text":
        content += "\n"

    # Long lines that is a full sentence
    # or having periods that is not bullet points
    if line_text.endswith(".") and line_length > 1: # Sometimes bullet points are chopped into "1.", "2.",...
        content += line_text + "\n"

    # Long lines that are continuous
    elif last_char.isalpha():
        content += " " + line_text # If no spacing at the end
    else:
        content += line_text + " "

    previous_type = "long text"
    
    return content, previous_type

def append_line(content: str, previous_type: str, line_text: str):
    """Parse text content"""

    words = line_text.split()
    line_length = len(words)
    
    # Short line with size < 7
    if line_length in range(1, 7):
        if not is_bullet(line_text):
            # Short lines, not bullets
            content, previous_type = append_short_line(content, line_text, previous_type)
        else:
            # Short lines that have bullet points
            content += "\n" + line_text + " "
            previous_type = "bullet"

    # Long line with size >= 7
    else:
        content, previous_type = append_long_line(content, line_text, line_length, previous_type)

    return content, previous_type



def extract_table(page, page_number) -> list:
    """Extract table iamges and coords"""
    
    table_coords = defaultdict(list) # List of table coords
    os.makedirs(Path(OUTPUT_DIR_PATH), exist_ok=True)

    with pdfplumber.open(Path(INPUT_PDF_PATH)) as pdf:
        page = pdf.pages[page_number - 1]
        tables = page.find_tables()
        
    for table_index, table in enumerate(tables, start=1):
        
        file_name = f"page_{page_number}_table_{table_index}.png"
        table_img_path = Path(OUTPUT_DIR_PATH) / f"{page_number}" / "table_img" / file_name
        table_img_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Clip bbox to page bounds
        x0, y0, x1, y1 = table.bbox
        table_coords[page_number].append({
            "coords": [x0, y0, x1, y1],
            "path": table_img_path
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
        table_img = cropped_page.to_image(resolution = PDF_RESOLUTION)
        table_img.save(table_img_path, format="PNG")

        print(f"Saved page {page_number}, table {table_index} → {table_img_path}")
            
    return table_coords               
                   
def extract_text(doc, page, page_number, table_coords):
    """Extract all text content of a page"""
    
    table_exist = False # Flag to extract path later
    table_folder_path = None
    text_dict = page.get_text("dict") # Full page content
    table_bboxes = table_coords.get(page_number, []) # Table coords of a page
    content = f"# Page {page_number}\n\n" # Top of text file is page number
    
    # Text file path
    text_file_path = Path(OUTPUT_DIR_PATH) / f"{page_number}" / f"page_{page_number}_text.md"
    text_file_path.parent.mkdir(parents=True, exist_ok=True)

    
    for block in text_dict["blocks"]:
        if block["type"] != 0:  # Only text blocks
            continue
    
        rect = fitz.Rect(*block["bbox"]) # Bounding box of block

        # Skipping overlapped table + flag table exists
        if any(rect.intersects(fitz.Rect(*tb["coords"])) for tb in table_bboxes):
            if table_exist == False:
                table_folder_path = Path(OUTPUT_DIR_PATH) / f"{page_number}" / "table_img"
                table_exist = True
            continue
        
        previous_type = "" # Track each parsed line types
        
        # Parse each line in a block
        for line in block["lines"]:
            line_text = "".join(span["text"] for span in line["spans"]).strip()
            if not line_text:  # Skip empty lines
                continue
            if re.fullmatch(r"\d+", line_text.strip()) and rect.y1 > page.rect.height * 0.9:
                continue  # Skip footer page number

            # Process and form full text content
            content, previous_type = append_line(content, previous_type, line_text)
            
              

    # Save to Markdown
    text_file_path = Path(OUTPUT_DIR_PATH) / f"{page_number}" / f"page_{page_number}_text.md"
    text_file_path.parent.mkdir(parents=True, exist_ok=True)

    # Sort numeric list
    content = fix_bullet_list(content)
    
    # LLM-based post-processing
    if table_exist:
        content = extract_page(content, table_folder_path) # LLM reformat + extract table text
    else:
        content = validate_parser(content) # LLM reformat
    
    # Write text content into .md files
    with open(text_file_path, "w", encoding="utf-8") as md_file:
        md_file.write(content)

    # Append table path into .md text files
    with open(text_file_path, "a", encoding="utf-8") as md_file:
        md_file.write("\n")
        for tb in table_bboxes:
            md_file.write(f"[Schema](table_img/{tb['path'].name})\n")
            
    # Extract images
    extract_image(doc, page, text_file_path, page_number)

def extract_image(doc, page, text_file_path, page_number):
    """
    Extract images in a page, filtering out small design elements 
    based on their area relative to the page area.
    """
    
    img_paths = []
    
    # 1. Calculate Page Area
    page_area = page.rect.width * page.rect.height
    
    # Calculate the minimum required image area
    min_image_area = page_area * MIN_AREA_RATIO
    
    for img_index, img in enumerate(page.get_images(full=True)):
        xref = img[0]
        
        # --- 2. GET IMAGE ON-PAGE AREA ---
        image_rects = page.get_image_rects(xref)
        
        if not image_rects:
            continue
            
        # Get the dimensions of the primary placement (first rectangle)
        image_rect = image_rects[0]
        image_area_on_page = image_rect.width * image_rect.height

        # --- 3. APPLY AREA FILTER ---
        # Skip the image if its area is less than the minimum required area.
        if image_area_on_page < min_image_area:
            continue # This is a small design element, skip extraction
            
        # --- ORIGINAL EXTRACTION LOGIC CONTINUES ---
        pix = fitz.Pixmap(doc, xref)
        
        # Note: 'Path(OUTPUT_DIR_PATH)' is an external variable assumed to be defined by the caller
        img_path = Path(OUTPUT_DIR_PATH) / f"{page_number}" / f"page_{page_number}_img_{img_index}.png"
        img_path.parent.mkdir(parents=True, exist_ok=True)
        
        if pix.n >= 5: 
            pix = fitz.Pixmap(fitz.csRGB, pix) # Pixel map
            
        pix.save(img_path)
        img_paths.append(img_path)
        
    # Append image paths into .md text files
    with open(text_file_path, "a", encoding="utf-8") as md_file:
        md_file.write("\n")
        for path in img_paths:
            md_file.write(f"[Schema]({path.name})\n")
    


if __name__ == "__main__":
    doc = fitz.open(Path(INPUT_PDF_PATH)) # Read pdf with fitz
    
    page_number = 38
    page = doc[page_number] # One page pass
    
    """Step 1: Extract table images and their coordinates"""
    table_coords = extract_table(page, page_number + 1)
    
    """Step 2: Extract all text, reformat with LLM and append table paths"""
    extract_text(doc, page, page_number + 1, table_coords)
    
    """Step 3: Extract all images, filter, then append image paths"""
    text_file_path = Path(OUTPUT_DIR_PATH) / f"{page_number + 1}" / f"page_{page_number + 1}_text.md"
    text_file_path.parent.mkdir(parents=True, exist_ok=True)
    extract_image(doc, page, text_file_path, page_number + 1)
