import json
from google import generativeai as genai
from prompt import prompt_val

# Load ground truth
with open("test_json/test_ground_truth.JSON", "r", encoding="utf-8") as f:
    ground_truth = json.load(f)

# Load generated answers
with open("test_json/test_generated.JSON", "r", encoding="utf-8") as f:
    generated = json.load(f)

# Create a dictionary for quick lookup
gen_dict = {item["question"]: item["answer"] for item in generated}

# Your evaluation prompt (the one I gave earlier)
evaluation_prompt = prompt_val

# Initialize Gemini
genai.configure(api_key="AIzaSyBy0lq6xWF1JZoTUZ_K2Lqf9v5ShQhWHp0")
model = genai.GenerativeModel("gemini-2.5-flash")

# Run evaluation for each pair
results = []
for gt in ground_truth:
    q = gt["question"]
    gt_answer = gt["answer"]
    ga = gen_dict.get(q, "")  # map by question text

    input_text = f"Question: {q}\nGround Truth Answer: {gt_answer}\nGenerated Answer: {ga}"

    response = model.generate_content([
        {"role": "user", "parts": [{"text": evaluation_prompt}]},
        {"role": "user", "parts": [{"text": input_text}]}
    ])


    # Parse model response as JSON
    try:
        evaluation = json.loads(response.text)
    except:
        evaluation = {"error": "Failed to parse", "raw": response.text}

    results.append({
        "question": q,
        "ground_truth": gt_answer,
        "generated_answer": ga,
        "evaluation": evaluation
    })

# Save results
with open("test_json/evaluations.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
