import os
from google import genai

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def summarize_text(text: str) -> str:
    if not text or len(text.split()) < 30:
        return "The audio is too short to generate a meaningful summary."

    prompt = f"""
    You are generating professional meeting minutes.

    Output format (strict):
    OVERALL AUDIO/MEETING FILE SUMMARY :
    - bullet points
    - Keep every details without missing any information
    ACTION ITEMS:
    - bullet points with owner if mentioned like this -> Owner name only: Task 
    - if no action items, write "None"

    Rules:
    - Use '-' for bullet points
    - Do not add extra text or explanations

    Transcript:
    {text}"""
    
    response = client.models.generate_content(
        model="models/gemini-2.5-flash", 
        contents=prompt)

    return response.text.strip()
