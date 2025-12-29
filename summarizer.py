def summarize_text(text: str) -> str:

    lines = text.split(".")
    important_lines = lines[:5]

    summary = "• " + "\n• ".join(line.strip() for line in important_lines if line.strip())
    return summary