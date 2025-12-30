import os
from google import genai

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def summarize_text(text: str) -> str:
    if not text or len(text.split()) < 30:
        return "The audio is too short to generate a meaningful summary."

    prompt = f"""
    You are an AI assistant generating professional meeting minutes.

    Rules:
    - Output ONLY bullet points
    - Do NOT add headings, introductions, or explanations
    - If no decisions or action items are present, explicitly say "None"

    Generate concise bullet points covering:
    - Main topics discussed
    - Key decisions
    - Conclusions
    - Action items (if any)

    Transcript:
    {text}
    """
    
    response = client.models.generate_content(
        model="models/gemini-2.5-flash", 
        contents=prompt)

    return response.text.strip()
