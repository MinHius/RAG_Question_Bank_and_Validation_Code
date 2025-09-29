import json
from google import generativeai as genai
from prompt import prompt_val, prompt_pdf
from config import GEMINI_API_KEY, GEMINI_MODEL


def validate_RAG():
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
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)

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


def validate_parser(text, page_num):
    evaluation_prompt = prompt_pdf

    # Initialize Gemini
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)

    # Run evaluation for each pair

    input_text = f"Prompt: {evaluation_prompt} \n\n Parsed text: {text}"

    response = model.generate_content(input_text)
    response_text = response.text if hasattr(response, "text") else str(response)
    # file_path = f"test_val/{page_num}.md"

    # with open(file_path, "w", encoding="utf-8") as md_file:
    #     md_file.write(response_text)
    
    return response_text
        