import io
import zipfile

import pytest

from app.services.resume_parser import (
    UnreadableDocumentError,
    UnsupportedDocumentError,
    clean_text,
    parse_document,
)


def test_parse_docx_includes_tables(docx_bytes):
    document = parse_document(docx_bytes, "resume.docx")
    assert document.source_format == "docx"
    assert "Alex Rivera" in document.text
    assert "B.Tech in Computer Science" in document.text
    assert "Kubernetes" in document.text
    assert document.lines


def test_parse_pdf(pdf_bytes):
    document = parse_document(pdf_bytes, "resume.pdf")
    assert document.source_format == "pdf"
    assert document.page_count == 1
    assert "Alex Rivera" in document.text
    assert not document.is_scanned


def test_parse_blank_pdf_is_scanned(blank_pdf_bytes):
    document = parse_document(blank_pdf_bytes, "resume.pdf")
    assert document.is_scanned is True


def test_reject_legacy_doc():
    with pytest.raises(UnsupportedDocumentError):
        parse_document(b"anything", "resume.doc")


def test_reject_fake_pdf():
    with pytest.raises(UnsupportedDocumentError):
        parse_document(b"not a pdf", "resume.pdf")


def test_reject_fake_docx():
    with pytest.raises(UnsupportedDocumentError):
        parse_document(b"not a zip", "resume.docx")


def test_reject_invalid_docx_zip():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("hello.txt", "not a document")
    with pytest.raises(UnsupportedDocumentError):
        parse_document(buffer.getvalue(), "resume.docx")


def test_filename_none_uses_content_type(pdf_bytes):
    document = parse_document(pdf_bytes, None, content_type="application/pdf")
    assert document.source_format == "pdf"


def test_empty_file_rejected():
    with pytest.raises(UnreadableDocumentError):
        parse_document(b"", "resume.pdf")


def test_clean_text_preserves_lines():
    assert clean_text("Hello\r\n\r\nWorld\tAgain") == "Hello\nWorld Again"
