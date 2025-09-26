import fitz  # PyMuPDF

def draw_bounding_boxes(pdf_path, out_dir="bbox_pages"):
    import os
    os.makedirs(out_dir, exist_ok=True)
    doc = fitz.open(pdf_path)

    for i, page in enumerate(doc, start=1):
        # Make a copy of the page as a pixmap
        pix = page.get_pixmap(dpi=150)  
        # New page for drawing (vector overlay)
        page_new = doc[i-1]  

        for block in page.get_text("blocks"):
            x0, y0, x1, y1, text, *_ = block
            rect = fitz.Rect(x0, y0, x1, y1)
            page_new.draw_rect(rect, color=(1, 0, 0), width=0.7)

        # Save annotated image
        pix = page_new.get_pixmap(dpi=150)
        out_path = f"{out_dir}/{i}.png"
        pix.save(out_path)
        print(f"Saved {out_path}")


# Example usage
draw_bounding_boxes("C:/Users/Dell/Desktop/TÀI LIỆU ĐÀO TẠO AN TOÀN THÔNG TIN 2025.pdf")
