def text_and_image():
    doc = fitz.open(input_file)
    for page_count, page in enumerate(doc, start=1):
        # Extract dict (structured)
        text_dict = page.get_text("dict")
        print(type(page))
        
        # Page as PNG
        pix = page.get_pixmap()
        img = pix.tobytes("png")