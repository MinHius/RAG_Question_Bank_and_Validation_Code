import google.generativeai as genai
from config import GEMINI_API_KEY, GEMINI_MODEL

genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel(GEMINI_MODEL)  # or gemini-1.5-pro

# Open the PNG as bytes
with open("table/slide36_table.png", "rb") as f:
    image_bytes = f.read()

# Send image + text prompt together
response = model.generate_content(
    [
        {"mime_type": "image/png", "data": image_bytes},  # image
        "Please extract the text from this table, and return a markdown table."        # text prompt
    ]
)

print(response.text)
