import time
import tracemalloc
import zipfile
from email.message import EmailMessage
from io import BytesIO

from django.core.files.storage import FileSystemStorage

import pytest
from openpyxl import Workbook

from baserow.core.limited_process import LimitedProcessFailed
from baserow.core.user_files.handler import UserFileHandler
from baserow.core.user_files.registries import file_text_extractor_registry
from baserow.test_utils.helpers import (
    PEOPLE_XLS,
    build_deeply_nested_docx,
    build_docx,
    build_pdf,
    build_slow_pdf,
)


def build_zip(files: dict[str, str]) -> bytes:
    output = BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return output.getvalue()


def build_pptx_slide(*paragraphs: str) -> str:
    namespace = "http://schemas.openxmlformats.org/drawingml/2006/main"
    body = "".join(f"<a:p><a:r><a:t>{text}</a:t></a:r></a:p>" for text in paragraphs)
    return f'<p:sld xmlns:a="{namespace}" xmlns:p="presentation">{body}</p:sld>'


def build_open_document(body: str) -> bytes:
    return build_zip(
        {
            "content.xml": (
                "<office:document-content "
                'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
                'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
                'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
                'xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0">'
                f"<office:body>{body}</office:body></office:document-content>"
            )
        }
    )


def build_xlsx(sheets: dict[str, list[list]]) -> bytes:
    workbook = Workbook()
    workbook.remove(workbook.active)
    for sheet_name, rows in sheets.items():
        sheet = workbook.create_sheet(sheet_name)
        for row in rows:
            sheet.append(row)
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


@pytest.mark.parametrize(
    "mime_type,file_name,extractor_type",
    [
        ("text/plain", "notes.txt", "plain_text"),
        ("", "data.csv", "plain_text"),
        ("application/json", "data", "plain_text"),
        ("text/html", "page.html", "html"),
        ("", "page.htm", "html"),
        ("application/pdf", "document", "pdf"),
        ("", "document.pdf", "pdf"),
        (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "document",
            "word",
        ),
        ("", "Report.DOCX", "word"),
        ("application/vnd.ms-excel", "data", "spreadsheet"),
        ("", "data.xlsx", "spreadsheet"),
        ("", "data.xls", "spreadsheet"),
        ("application/vnd.ms-word.document.macroEnabled.12", "file", "word"),
        ("", "report.docm", "word"),
        ("", "template.dotx", "word"),
        ("application/vnd.ms-excel.sheet.macroEnabled.12", "file", "spreadsheet"),
        ("", "data.xlsm", "spreadsheet"),
        ("", "template.xltx", "spreadsheet"),
        (
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "file",
            "powerpoint",
        ),
        ("", "slides.pptx", "powerpoint"),
        ("application/vnd.oasis.opendocument.text", "file", "open_document"),
        ("", "document.odt", "open_document"),
        ("", "data.ods", "open_document"),
        ("", "slides.odp", "open_document"),
        ("message/rfc822", "file", "email"),
        ("", "mail.eml", "email"),
        ("application/epub+zip", "book.epub", None),
        ("application/msword", "legacy.doc", None),
        ("image/png", "image.png", None),
        ("application/zip", "archive.zip", None),
    ],
)
def test_get_file_text_extractor(mime_type, file_name, extractor_type):
    extractor = file_text_extractor_registry.get_for_file(mime_type, file_name)
    assert getattr(extractor, "type", None) == extractor_type


def test_extract_text():
    plain_text = file_text_extractor_registry.get("plain_text")
    assert plain_text.extract(BytesIO("Héllo world".encode()), 5) == "Héllo"

    html = file_text_extractor_registry.get("html")
    assert (
        html.extract(
            BytesIO(
                b"<html><head><title>Title</title><style>p{}</style></head>"
                b"<body><p>Hello</p><script>alert(1)</script><p>world</p></body>"
                b"</html>"
            ),
            100,
        )
        == "Hello\nworld"
    )

    pdf = file_text_extractor_registry.get("pdf")
    assert pdf.extract(BytesIO(build_pdf("Hello PDF")), 100) == "Hello PDF"


def test_extract_text_of_other_encodings():
    plain_text = file_text_extractor_registry.get("plain_text")
    text = "Le café du matin et le résumé de la réunion, naïve et élégante. " * 5

    assert plain_text.extract(BytesIO(text.encode("cp1252")), 1000) == text
    assert plain_text.extract(BytesIO(text.encode("utf-16")), 1000) == text
    assert plain_text.extract(BytesIO(text.encode("utf-8-sig")), 1000) == text
    # Reading stops in the middle of the two bytes of the last "é".
    assert plain_text.extract(BytesIO("aé".encode()[:2]), 1) == "a"


def test_extract_word_text():
    word = file_text_extractor_registry.get("word")
    docx = build_docx(
        "<w:p><w:r><w:t>Hello </w:t></w:r><w:r><w:t>Word</w:t></w:r></w:p>"
        # Deleted text and field codes aren't visible.
        "<w:p><w:del><w:r><w:delText>removed</w:delText></w:r></w:del>"
        "<w:r><w:instrText>PAGE</w:instrText></w:r></w:p>"
        "<w:tbl><w:tr><w:tc><w:p><w:r><w:t>In a table</w:t></w:r></w:p></w:tc>"
        "</w:tr></w:tbl>"
        # A text box is a paragraph within a paragraph.
        "<w:p><w:r><w:t>Before</w:t></w:r><w:r><w:txbxContent><w:p><w:r>"
        "<w:t>In a box</w:t></w:r></w:p></w:txbxContent></w:r></w:p>"
    )

    assert (
        word.extract(BytesIO(docx), 100) == "Hello Word\nIn a table\nIn a box\nBefore"
    )
    assert word.extract(BytesIO(docx), 7) == "Hello W"


def test_extract_spreadsheet_text():
    spreadsheet = file_text_extractor_registry.get("spreadsheet")
    xlsx = build_xlsx(
        {
            "Customers": [["Name", "Orders"], ["Ada", 3], [None, None], ["Bob", 1.0]],
            "Notes": [["Call back", None, "tomorrow"]],
        }
    )

    assert spreadsheet.extract(BytesIO(xlsx), 1000) == (
        "Customers\nName\tOrders\nAda\t3\nBob\t1\nNotes\nCall back\ttomorrow"
    )
    assert spreadsheet.extract(BytesIO(xlsx), 13) == "Customers\nNam"
    assert spreadsheet.extract(BytesIO(PEOPLE_XLS), 1000) == (
        "People\nName\tAge\nAda\t36\nBob\t40"
    )


def test_extract_powerpoint_text():
    powerpoint = file_text_extractor_registry.get("powerpoint")
    pptx = build_zip(
        {
            "ppt/slides/slide10.xml": build_pptx_slide("Tenth"),
            "ppt/slides/slide2.xml": build_pptx_slide("Second"),
            "ppt/slides/slide1.xml": build_pptx_slide("Agenda", "Introduction"),
            "ppt/notesSlides/notesSlide1.xml": build_pptx_slide("Speaker notes"),
        }
    )

    assert (
        powerpoint.extract(BytesIO(pptx), 100) == "Agenda\nIntroduction\nSecond\nTenth"
    )
    assert powerpoint.extract(BytesIO(pptx), 8) == "Agenda\nI"


def test_extract_open_document_text():
    open_document = file_text_extractor_registry.get("open_document")
    document = build_open_document(
        "<office:text><text:h>Title</text:h>"
        "<text:p>Hello<text:s/>world<text:tab/>and<text:line-break/>more</text:p>"
        # A frame is a paragraph within a paragraph.
        "<text:p>Before<draw:frame><draw:text-box><text:p>In a frame</text:p>"
        "</draw:text-box></draw:frame></text:p></office:text>"
    )
    spreadsheet = build_open_document(
        '<office:spreadsheet><table:table table:name="Sheet">'
        "<table:table-row><table:table-cell><text:p>Name</text:p></table:table-cell>"
        "<table:table-cell/><table:table-cell><text:p>Age</text:p>"
        "</table:table-cell></table:table-row>"
        '<table:table-row table:number-rows-repeated="1000"><table:table-cell/>'
        "</table:table-row>"
        "<table:table-row><table:table-cell><text:p>Ada</text:p><text:p>Lovelace"
        "</text:p></table:table-cell><table:table-cell><text:p>36</text:p>"
        "</table:table-cell></table:table-row></table:table></office:spreadsheet>"
    )

    assert open_document.extract(BytesIO(document), 100) == (
        "Title\nHello world and more\nIn a frame\nBefore"
    )
    assert open_document.extract(BytesIO(spreadsheet), 100) == (
        "Name\tAge\nAda Lovelace\t36"
    )


@pytest.mark.parametrize(
    "extractor_type,build_file",
    [
        ("word", lambda: build_docx("<w:p/><w:sectPr/>" * 100_000)),
        (
            "open_document",
            lambda: build_open_document(
                "<office:spreadsheet><table:table>"
                + "<table:table-row><table:table-cell/></table:table-row>" * 100_000
                + "</table:table></office:spreadsheet>"
            ),
        ),
    ],
)
def test_extracting_many_elements_without_text_uses_bounded_memory(
    extractor_type, build_file
):
    extractor = file_text_extractor_registry.get(extractor_type)
    file = BytesIO(build_file())

    tracemalloc.start()
    try:
        assert extractor.extract(file, 1000) == ""
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert peak < 5 * 1024 * 1024


def test_extract_email_text():
    email = file_text_extractor_registry.get("email")
    message = EmailMessage()
    message["Subject"] = "Invoice overdue"
    message["From"] = "Ada <ada@example.com>"
    message["To"] = "bob@example.com"
    message.set_content("Please pay the invoice.")
    message.add_alternative("<p>Please pay the <b>invoice</b>.</p>", subtype="html")
    message.add_attachment(b"%PDF", maintype="application", subtype="pdf")
    html_message = EmailMessage()
    html_message["Subject"] = "Newsletter"
    html_message.set_content("<h1>News</h1><p>Read more</p>", subtype="html")

    assert email.extract(BytesIO(message.as_bytes()), 1000) == (
        "Subject: Invoice overdue\nFrom: Ada <ada@example.com>\n"
        "To: bob@example.com\n\nPlease pay the invoice."
    )
    assert email.extract(BytesIO(html_message.as_bytes()), 1000) == (
        "Subject: Newsletter\n\nNews\nRead more"
    )
    assert email.extract(BytesIO(message.as_bytes()), 7) == "Subject"


@pytest.mark.django_db
def test_user_file_handler_extract_text(data_fixture, tmpdir):
    user = data_fixture.create_user()
    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    handler = UserFileHandler()
    text_file = handler.upload_user_file(
        user, "notes.txt", BytesIO(b"Some notes"), storage=storage
    )
    image_file = handler.upload_user_file(
        user, "file.bin", BytesIO(b"\x00\x01"), storage=storage
    )

    assert (
        handler.extract_text(text_file.name, "text/plain", 100, storage=storage)
        == "Some notes"
    )
    assert (
        handler.extract_text(
            image_file.name, "application/octet-stream", 100, storage=storage
        )
        is None
    )


@pytest.mark.django_db
def test_user_file_handler_stops_extracting_hostile_files(data_fixture, tmpdir):
    user = data_fixture.create_user()
    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    handler = UserFileHandler()
    nested_docx = handler.upload_user_file(
        user, "nested.docx", BytesIO(build_deeply_nested_docx()), storage=storage
    )
    slow_pdf = handler.upload_user_file(
        user, "slow.pdf", BytesIO(build_slow_pdf()), storage=storage
    )

    with pytest.raises(LimitedProcessFailed):
        handler.extract_text(nested_docx.name, "", 1000, storage=storage)

    start = time.monotonic()
    with pytest.raises(LimitedProcessFailed):
        handler.extract_text(
            slow_pdf.name, "application/pdf", 1000, timeout_seconds=1, storage=storage
        )
    assert time.monotonic() - start < 5
