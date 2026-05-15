import re


def clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    if overlap >= chunk_size:
        overlap = max(0, chunk_size // 5)

    normalized = clean_text(text)
    if not normalized:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        chunk = normalized[start:end]

        if end < len(normalized):
            boundary = max(chunk.rfind(". "), chunk.rfind("\n"), chunk.rfind(" "))
            if boundary > chunk_size * 0.55:
                end = start + boundary + 1
                chunk = normalized[start:end]

        chunk = chunk.strip()
        if chunk:
            chunks.append(chunk)

        if end >= len(normalized):
            break
        start = max(0, end - overlap)

    return chunks
