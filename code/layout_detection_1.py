"""Paddle StructureV3 for images + PyMuPdf for text"""
from pathlib import Path
from paddleocr import PPStructureV3, PaddleOCR
import fitz


input_file = "C:/Users/Dell/Desktop/TÀI LIỆU ĐÀO TẠO AN TOÀN THÔNG TIN 2025.pdf"
output_path = Path("extracted_1")

# Paddle
pipeline = PPStructureV3(lang = "vi")
output = pipeline.predict(input = input_file, use_chart_recognition = True, use_table_recognition = True)

# PyMuPdf
doc = fitz.open(input_file)


markdown_images = []
for page_count, res in enumerate(output, start = 1):
    md_info = res.markdown
    
    # Images
    markdown_images.append(md_info.get("markdown_images", {}))
    # Text
    text = doc[page_count - 1].get_text("text")
    file_path = output_path / f"{page_count}" / f"page_{page_count}_text.md"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    content = f"# Page {page_count}\n\n" + text.strip() + "\n\n"

    # Saving text as .md files
    with open(file_path, "w", encoding="utf-8") as md_file:
        md_file.write(content)


for page_count, item in enumerate(markdown_images, start=1):
    if item:
        for img_idx, (path, image) in enumerate(item.items(), start=1):
            new_name = f"page_{page_count}_img{img_idx}.png"
            img_path = output_path / f"{page_count}" / new_name
            img_path.parent.mkdir(parents=True, exist_ok=True)
            
            image.save(img_path)  # save only when needed

            file_path = output_path / f"{page_count}" / f"page_{page_count}_text.md"
            with open(file_path, "a", encoding="utf-8") as md_file:
                md_file.write(f"[Schema]({img_path.name})\n")


print(f"Saved {len(doc)} pages into {output_path}")
doc.close()