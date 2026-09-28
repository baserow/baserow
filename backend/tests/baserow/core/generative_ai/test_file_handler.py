from baserow.core.generative_ai.registries import EmbedKindLimit, FileHandler
from baserow_premium.fields.ai_file import AIFile


def _make_ai_file(name: str, size: int, mime_type: str) -> AIFile:
    ai_file = AIFile(name=name, original_name=name, size=size, mime_type=mime_type)
    ai_file.read_content = lambda: b"content"  # type: ignore[assignment]
    return ai_file


class _ImageLimitedFileHandler(FileHandler):
    _EMBEDDABLE_EXTENSIONS = {".png", ".pdf"}
    _EMBED_KIND_LIMITS = (
        EmbedKindLimit(extensions=frozenset({".png"}), max_file_bytes=100, max_files=2),
    )


def test_embed_kind_limits_cap_file_size_and_count_per_kind():
    files = [
        _make_ai_file("a.png", 50, "image/png"),
        _make_ai_file("too-big.png", 101, "image/png"),
        _make_ai_file("b.png", 100, "image/png"),
        _make_ai_file("third.png", 50, "image/png"),
        _make_ai_file("unlimited.pdf", 500, "application/pdf"),
    ]

    prepared = _ImageLimitedFileHandler().prepare_files(files)

    assert [ai_file.name for ai_file in prepared] == ["a.png", "b.png", "unlimited.pdf"]


def test_file_handler_without_kind_limits_embeds_every_matching_file():
    class _UnlimitedFileHandler(FileHandler):
        _EMBEDDABLE_EXTENSIONS = {".png"}

    files = [_make_ai_file(f"{index}.png", 1000, "image/png") for index in range(3)]

    prepared = _UnlimitedFileHandler().prepare_files(files)

    assert len(prepared) == 3
