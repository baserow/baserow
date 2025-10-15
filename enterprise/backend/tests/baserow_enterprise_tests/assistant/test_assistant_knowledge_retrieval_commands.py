import tempfile
import zipfile
from pathlib import Path

from django.core.management import call_command

import pytest

from baserow_enterprise.assistant.models import (
    KnowledgeBaseCategory,
    KnowledgeBaseChunk,
    KnowledgeBaseDocument,
)


@pytest.mark.django_db
class TestKnowledgeBaseCommands:
    """Test the dump_knowledge_base and load_knowledge_base management commands"""

    @pytest.fixture(autouse=True)
    def init_vector_field(self):
        KnowledgeBaseChunk.try_init_vector_field()

    @pytest.fixture
    def single_document_data(self):
        """Create a single document with 1 category and 1 chunk"""

        category = KnowledgeBaseCategory.objects.create(
            name="Test Category", description="Test category description"
        )
        document = KnowledgeBaseDocument.objects.create(
            title="Test Document",
            slug="test-doc",
            raw_content="Test content",
            content="Test content",
            category=category,
            status=KnowledgeBaseDocument.Status.READY,
        )
        chunk = KnowledgeBaseChunk.objects.create(
            source_document=document,
            content="Test chunk content",
            index=0,
            embedding=[1.0] * KnowledgeBaseChunk.EMBEDDING_DIMENSIONS,
            metadata={"test": "data"},
        )
        return {"category": category, "document": document, "chunk": chunk}

    @pytest.fixture
    def multiple_document_data(self):
        """Create multiple documents with different statuses for testing --all option"""

        category = KnowledgeBaseCategory.objects.create(
            name="Test Category", description="Test category description"
        )

        # Ready document (should be included in normal dump)
        ready_document = KnowledgeBaseDocument.objects.create(
            title="Ready Document",
            slug="ready-doc",
            raw_content="Ready content",
            content="Ready content",
            category=category,
            status=KnowledgeBaseDocument.Status.READY,
        )
        ready_chunk = KnowledgeBaseChunk.objects.create(
            source_document=ready_document,
            content="Ready chunk content",
            index=0,
            embedding=[1.0] * KnowledgeBaseChunk.EMBEDDING_DIMENSIONS,
            metadata={"test": "ready"},
        )

        # Processing document (should only be included with --all)
        processing_document = KnowledgeBaseDocument.objects.create(
            title="Processing Document",
            slug="processing-doc",
            raw_content="Processing content",
            content="Processing content",
            category=category,
            status=KnowledgeBaseDocument.Status.PROCESSING,
        )
        processing_chunk = KnowledgeBaseChunk.objects.create(
            source_document=processing_document,
            content="Processing chunk content",
            index=0,
            embedding=[2.0] * KnowledgeBaseChunk.EMBEDDING_DIMENSIONS,
            metadata={"test": "processing"},
        )

        return {
            "category": category,
            "ready_document": ready_document,
            "ready_chunk": ready_chunk,
            "processing_document": processing_document,
            "processing_chunk": processing_chunk,
        }

    def test_dump_and_load_basic(self, single_document_data):
        """Test basic dump and load functionality with zip files"""

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            temp_file = f.name

        try:
            # Dump
            call_command("dump_knowledge_base", temp_file, force=True)

            # Verify file is a valid zip file
            with zipfile.ZipFile(temp_file, "r") as zf:
                assert len(zf.namelist()) > 0

            # Clear database
            KnowledgeBaseDocument.objects.all().delete()
            KnowledgeBaseCategory.objects.all().delete()

            # Load
            call_command("load_knowledge_base", temp_file)

            # Verify
            assert KnowledgeBaseCategory.objects.filter(name="Test Category").exists()
            assert KnowledgeBaseDocument.objects.filter(slug="test-doc").exists()
            assert KnowledgeBaseChunk.objects.filter(
                content="Test chunk content"
            ).exists()

        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_dump_with_force_overwrites_existing_file(self, single_document_data):
        """Test that --force option overwrites existing files"""

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            temp_file = f.name

        try:
            # Create an existing file
            with open(temp_file, "w") as f:
                f.write("existing content")

            # Dump without --force should fail or warn
            # (behavior depends on implementation, but should not overwrite)
            result_code = call_command("dump_knowledge_base", temp_file)

            # Now dump with --force should succeed
            call_command("dump_knowledge_base", temp_file, force=True)

            # Verify file was overwritten and is now a valid zip
            with zipfile.ZipFile(temp_file, "r") as zf:
                assert len(zf.namelist()) > 0

        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_dump_with_all_includes_non_ready_documents(self, multiple_document_data):
        """Test that --all option includes documents with non-READY status"""

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            temp_file_normal = f.name
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            temp_file_all = f.name

        try:
            # Dump without --all (should only include READY documents)
            call_command("dump_knowledge_base", temp_file_normal, force=True)

            # Dump with --all (should include all documents)
            call_command("dump_knowledge_base", temp_file_all, all=True, force=True)

            # Clear database
            KnowledgeBaseDocument.objects.all().delete()
            KnowledgeBaseCategory.objects.all().delete()

            # Load normal dump
            call_command("load_knowledge_base", temp_file_normal)

            # Should only have ready document
            assert KnowledgeBaseDocument.objects.filter(slug="ready-doc").exists()
            assert not KnowledgeBaseDocument.objects.filter(
                slug="processing-doc"
            ).exists()

            # Clear database again
            KnowledgeBaseDocument.objects.all().delete()
            KnowledgeBaseCategory.objects.all().delete()

            # Load --all dump
            call_command("load_knowledge_base", temp_file_all)

            # Should have both documents
            assert KnowledgeBaseDocument.objects.filter(slug="ready-doc").exists()
            assert KnowledgeBaseDocument.objects.filter(slug="processing-doc").exists()

        finally:
            Path(temp_file_normal).unlink(missing_ok=True)
            Path(temp_file_all).unlink(missing_ok=True)

    def test_load_with_reset_deletes_existing_documents(self, single_document_data):
        """Test that --reset option deletes existing documents before loading"""

        # Create another document that should be deleted
        other_category = KnowledgeBaseCategory.objects.create(
            name="Other Category", description="Other category"
        )
        other_document = KnowledgeBaseDocument.objects.create(
            title="Other Document",
            slug="other-doc",
            raw_content="Other content",
            content="Other content",
            category=other_category,
        )

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            temp_file = f.name

        try:
            # Dump original data
            call_command("dump_knowledge_base", temp_file, force=True)

            # Load with --reset
            call_command("load_knowledge_base", temp_file, reset=True)

            # Verify original document exists
            assert KnowledgeBaseDocument.objects.filter(slug="test-doc").exists()

            # Verify other document was deleted
            assert not KnowledgeBaseDocument.objects.filter(slug="other-doc").exists()
            assert not KnowledgeBaseCategory.objects.filter(
                name="Other Category"
            ).exists()

        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_load_without_reset_preserves_existing_documents(
        self, single_document_data
    ):
        """Test that loading without --reset preserves existing documents"""

        # Create another document that should be preserved
        other_category = KnowledgeBaseCategory.objects.create(
            name="Other Category", description="Other category"
        )
        other_document = KnowledgeBaseDocument.objects.create(
            title="Other Document",
            slug="other-doc",
            raw_content="Other content",
            content="Other content",
            category=other_category,
            status=KnowledgeBaseDocument.Status.READY,
        )

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            temp_file = f.name

        try:
            # Dump original data (only test-doc)
            call_command("dump_knowledge_base", temp_file, force=True)

            # Clear only the test document
            KnowledgeBaseDocument.objects.filter(slug="test-doc").delete()
            KnowledgeBaseCategory.objects.filter(name="Test Category").delete()

            # Load without --reset
            call_command("load_knowledge_base", temp_file)

            # Verify both documents exist
            assert KnowledgeBaseDocument.objects.filter(slug="test-doc").exists()
            assert KnowledgeBaseDocument.objects.filter(slug="other-doc").exists()
            assert KnowledgeBaseCategory.objects.filter(name="Test Category").exists()
            assert KnowledgeBaseCategory.objects.filter(name="Other Category").exists()

        finally:
            Path(temp_file).unlink(missing_ok=True)
