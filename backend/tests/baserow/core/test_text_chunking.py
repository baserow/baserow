import pytest

from baserow.core.text_chunking import split_text


@pytest.mark.parametrize(
    "content", ["x" * 3100, "词" * 3100, "word " * 700, "line\n\n" * 700]
)
def test_split_text_covers_content_with_bounded_chunks(content):
    chunks = list(split_text(content, 1000, 150))

    assert chunks[0][0] == 0
    assert chunks[-1][1] == len(content)
    covered = set()
    for start, end, text in chunks:
        assert end - start <= 1000
        assert text == content[start:end]
        covered.update(range(start, end))
    assert len(covered) == len(content)


def test_split_text_overlaps_on_word_boundaries():
    chunks = list(split_text("one two three four five six", 12, 5))

    assert [text for _, _, text in chunks] == [
        "one two ",
        "two three ",
        "four five ",
        "six",
    ]


@pytest.mark.parametrize("overlap", [600, 1000, 2000])
def test_split_text_progresses_when_the_overlap_is_large(overlap):
    content = "word " * 700

    chunks = list(split_text(content, 1000, overlap))

    assert chunks[-1][1] == len(content)
    assert all(
        next_start > start
        for (start, _, _), (next_start, _, _) in zip(chunks, chunks[1:])
    )


def test_split_empty_text():
    assert list(split_text("", 1000, 150)) == []
