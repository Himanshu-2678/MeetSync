from transformers import pipeline

## loading the summarization pipeline
summarizer = pipeline("text2text-generation", model="google/flan-t5-base")


def summarize_text(text: str) -> str:

    if len(text.split()) < 30:
        return "The audio is too short to generate a meaningful summary."

    prompt = (
        "Explain the main idea of the following meeting or speech in a concise way. "
        "Mention what it is about and the conclusion if present:\n\n"
        f"{text}"
    )

    result = summarizer(
        prompt,
        max_length=150,
        do_sample=False
    )

    return result[0]["generated_text"]