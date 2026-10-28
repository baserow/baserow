from typing import Iterator


def split_text(content: str, size: int, overlap: int) -> Iterator[tuple[int, int, str]]:
    """
    Yields `(start, end, text)` slices of at most `size` characters, overlapping by
    roughly `overlap` characters so that a sentence on a boundary remains findable.
    Slices end on a paragraph, line or word boundary when one exists in the second
    half of the window.

    :param content: The text to split.
    :param size: The maximum number of characters of a slice.
    :param overlap: The number of characters that consecutive slices share.
    :return: The start and end position and the text of every slice.
    """

    start = 0
    while start < len(content):
        end = min(start + size, len(content))
        if end < len(content):
            for separator in ("\n\n", "\n", " "):
                boundary = content.rfind(separator, start + size // 2, end)
                if boundary >= 0:
                    end = boundary + len(separator)
                    break
        yield start, end, content[start:end]
        if end == len(content):
            break
        # Always progresses, also when the overlap isn't smaller than the slice.
        start = max(end - overlap, start + 1)
        # Start at a word boundary within the overlap when possible. If a word,
        # code block or URL is very long, the hard character bound still progresses.
        boundary = content.find(" ", start, end)
        if boundary >= 0:
            start = boundary + 1
