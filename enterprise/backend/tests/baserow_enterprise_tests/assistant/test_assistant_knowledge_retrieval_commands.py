import bz2
import gzip
import json
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

from django.core.management import call_command

import pytest
import yaml
from freezegun import freeze_time

from baserow_enterprise.assistant.models import (
    KnowledgeBaseCategory,
    KnowledgeBaseChunk,
    KnowledgeBaseDocument,
)

from .utils import TestVectorStore


@pytest.mark.django_db
class TestKnowledgeBaseCommands:
    """Test the dump_knowledge_base and load_knowledge_base management commands"""

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
            embedding=[1.0, 2.0, 3.0],
            metadata={"test": "data"},
        )
        return {"category": category, "document": document, "chunk": chunk}

    @patch(
        "baserow_enterprise.assistant.capabilities.knowledge_retrieval.handler.VectorStore"
    )
    def test_dump_and_load_json(self, mock_vector_store, single_document_data):
        """Test dump and load with JSON format"""

        mock_vector_store.return_value = TestVectorStore()

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_file = f.name

        try:
            # Dump
            call_command("dump_knowledge_base", temp_file, format="json")

            # Verify file is valid JSON
            with open(temp_file, "r") as f:
                data = json.load(f)
                assert isinstance(data, list)
                assert len(data) > 0

            # Clear database
            KnowledgeBaseDocument.objects.all().delete()
            KnowledgeBaseCategory.objects.all().delete()

            # Load
            call_command("load_knowledge_base", temp_file, format="json")

            # Verify
            assert KnowledgeBaseCategory.objects.filter(name="Test Category").exists()
            assert KnowledgeBaseDocument.objects.filter(slug="test-doc").exists()
            assert KnowledgeBaseChunk.objects.filter(
                content="Test chunk content"
            ).exists()

        finally:
            Path(temp_file).unlink(missing_ok=True)

    @patch(
        "baserow_enterprise.assistant.capabilities.knowledge_retrieval.handler.VectorStore"
    )
    def test_dump_and_load_xml(self, mock_vector_store, single_document_data):
        """Test dump and load with XML format"""

        mock_vector_store.return_value = TestVectorStore()

        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
            temp_file = f.name

        try:
            # Dump
            call_command("dump_knowledge_base", temp_file, format="xml")

            # Verify file is valid XML
            with open(temp_file, "r") as f:
                content = f.read()
                assert content.startswith("<?xml")
                # Parse to ensure it's well-formed XML
                ET.fromstring(content)

            # Clear database
            KnowledgeBaseDocument.objects.all().delete()
            KnowledgeBaseCategory.objects.all().delete()

            # Load
            call_command("load_knowledge_base", temp_file, format="xml")

            # Verify
            assert KnowledgeBaseCategory.objects.filter(name="Test Category").exists()
            assert KnowledgeBaseDocument.objects.filter(slug="test-doc").exists()
            assert KnowledgeBaseChunk.objects.filter(
                content="Test chunk content"
            ).exists()

        finally:
            Path(temp_file).unlink(missing_ok=True)

    @patch(
        "baserow_enterprise.assistant.capabilities.knowledge_retrieval.handler.VectorStore"
    )
    def test_dump_and_load_yaml(self, mock_vector_store, single_document_data):
        """Test dump and load with YAML format"""

        mock_vector_store.return_value = TestVectorStore()

        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            temp_file = f.name

        try:
            # Dump
            call_command("dump_knowledge_base", temp_file, format="yaml")

            # Verify file is valid YAML
            with open(temp_file, "r") as f:
                data = yaml.safe_load(f)
                assert isinstance(data, list)
                assert len(data) > 0

            # Clear database
            KnowledgeBaseDocument.objects.all().delete()
            KnowledgeBaseCategory.objects.all().delete()

            # Load
            call_command("load_knowledge_base", temp_file, format="yaml")

            # Verify
            assert KnowledgeBaseCategory.objects.filter(name="Test Category").exists()
            assert KnowledgeBaseDocument.objects.filter(slug="test-doc").exists()
            assert KnowledgeBaseChunk.objects.filter(
                content="Test chunk content"
            ).exists()

        finally:
            Path(temp_file).unlink(missing_ok=True)

    @patch(
        "baserow_enterprise.assistant.capabilities.knowledge_retrieval.handler.VectorStore"
    )
    def test_dump_and_load_jsonl(self, mock_vector_store, single_document_data):
        """Test dump and load with JSONL format"""

        mock_vector_store.return_value = TestVectorStore()

        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            temp_file = f.name

        try:
            # Dump
            call_command("dump_knowledge_base", temp_file, format="jsonl")

            # Verify file is valid JSONL (each line is valid JSON)
            with open(temp_file, "r") as f:
                lines = f.readlines()
                assert len(lines) > 0
                for line in lines:
                    line = line.strip()
                    if line:  # Skip empty lines
                        json.loads(line)  # Should not raise exception

            # Clear database
            KnowledgeBaseDocument.objects.all().delete()
            KnowledgeBaseCategory.objects.all().delete()

            # Load
            call_command("load_knowledge_base", temp_file, format="jsonl")

            # Verify
            assert KnowledgeBaseCategory.objects.filter(name="Test Category").exists()
            assert KnowledgeBaseDocument.objects.filter(slug="test-doc").exists()
            assert KnowledgeBaseChunk.objects.filter(
                content="Test chunk content"
            ).exists()

        finally:
            Path(temp_file).unlink(missing_ok=True)

    @patch(
        "baserow_enterprise.assistant.capabilities.knowledge_retrieval.handler.VectorStore"
    )
    def test_dump_and_load_gzip(self, mock_vector_store, single_document_data):
        """Test dump and load with gzip compression"""

        mock_vector_store.return_value = TestVectorStore()

        with tempfile.NamedTemporaryFile(suffix=".json.gz", delete=False) as f:
            temp_file = f.name

        try:
            # Dump
            call_command("dump_knowledge_base", temp_file, format="json")

            # Verify file is gzipped and contains valid JSON
            with gzip.open(temp_file, "rt") as f:
                data = json.load(f)
                assert isinstance(data, list)
                assert len(data) > 0

            # Clear database
            KnowledgeBaseDocument.objects.all().delete()
            KnowledgeBaseCategory.objects.all().delete()

            # Load
            call_command("load_knowledge_base", temp_file, format="json")

            # Verify
            assert KnowledgeBaseCategory.objects.filter(name="Test Category").exists()
            assert KnowledgeBaseDocument.objects.filter(slug="test-doc").exists()
            assert KnowledgeBaseChunk.objects.filter(
                content="Test chunk content"
            ).exists()

        finally:
            Path(temp_file).unlink(missing_ok=True)

    @patch(
        "baserow_enterprise.assistant.capabilities.knowledge_retrieval.handler.VectorStore"
    )
    def test_dump_and_load_bzip2(self, mock_vector_store, single_document_data):
        """Test dump and load with bzip2 compression"""

        mock_vector_store.return_value = TestVectorStore()

        with tempfile.NamedTemporaryFile(suffix=".json.bz2", delete=False) as f:
            temp_file = f.name

        try:
            # Dump
            call_command("dump_knowledge_base", temp_file, format="json")

            # Verify file is bzip2 compressed and contains valid JSON
            with bz2.open(temp_file, "rt") as f:
                data = json.load(f)
                assert isinstance(data, list)
                assert len(data) > 0

            # Clear database
            KnowledgeBaseDocument.objects.all().delete()
            KnowledgeBaseCategory.objects.all().delete()

            # Load
            call_command("load_knowledge_base", temp_file, format="json")

            # Verify
            assert KnowledgeBaseCategory.objects.filter(name="Test Category").exists()
            assert KnowledgeBaseDocument.objects.filter(slug="test-doc").exists()
            assert KnowledgeBaseChunk.objects.filter(
                content="Test chunk content"
            ).exists()

        finally:
            Path(temp_file).unlink(missing_ok=True)

    @patch(
        "baserow_enterprise.assistant.capabilities.knowledge_retrieval.handler.VectorStore"
    )
    def test_dump_and_load_zip(self, mock_vector_store, single_document_data):
        """Test dump and load with zip compression"""

        mock_vector_store.return_value = TestVectorStore()

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            temp_file = f.name

        try:
            # Dump
            call_command("dump_knowledge_base", temp_file, format="json")

            # Verify file is a valid zip file and contains the expected JSON file
            with zipfile.ZipFile(temp_file, "r") as zf:
                assert "knowledge_base.json" in zf.namelist()
                with zf.open("knowledge_base.json") as f:
                    data = json.load(f)
                    assert isinstance(data, list)
                    assert len(data) > 0

            # Clear database
            KnowledgeBaseDocument.objects.all().delete()
            KnowledgeBaseCategory.objects.all().delete()

            # Load
            call_command("load_knowledge_base", temp_file, format="json")

            # Verify
            assert KnowledgeBaseCategory.objects.filter(name="Test Category").exists()
            assert KnowledgeBaseDocument.objects.filter(slug="test-doc").exists()
            assert KnowledgeBaseChunk.objects.filter(
                content="Test chunk content"
            ).exists()

        finally:
            Path(temp_file).unlink(missing_ok=True)

    @patch(
        "baserow_enterprise.assistant.capabilities.knowledge_retrieval.handler.VectorStore"
    )
    def test_load_with_reset_deletes_existing_documents(
        self, mock_vector_store, single_document_data
    ):
        """Test that reset=True deletes other existing documents"""

        mock_vector_store.return_value = TestVectorStore()

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

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_file = f.name

        try:
            # Dump original data
            call_command(
                "dump_knowledge_base", temp_file, format="json", documents=["test-doc"]
            )

            # Load with reset=True
            call_command("load_knowledge_base", temp_file, format="json", reset=True)

            # Verify original document exists
            assert KnowledgeBaseDocument.objects.filter(slug="test-doc").exists()

            # Verify other document was deleted
            assert not KnowledgeBaseDocument.objects.filter(slug="other-doc").exists()
            assert not KnowledgeBaseCategory.objects.filter(
                name="Other Category"
            ).exists()

        finally:
            Path(temp_file).unlink(missing_ok=True)

    @patch(
        "baserow_enterprise.assistant.capabilities.knowledge_retrieval.handler.VectorStore"
    )
    def test_dry_run_does_not_change_anything(
        self, mock_vector_store, single_document_data
    ):
        """Test that dry_run=True doesn't change the database"""

        mock_vector_store.return_value = TestVectorStore()

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_file = f.name

        try:
            # Dump
            call_command("dump_knowledge_base", temp_file, format="json")

            # Clear database
            KnowledgeBaseDocument.objects.all().delete()
            KnowledgeBaseCategory.objects.all().delete()

            # Verify database is empty
            assert not KnowledgeBaseDocument.objects.exists()
            assert not KnowledgeBaseCategory.objects.exists()

            # Load with dry_run=True
            call_command("load_knowledge_base", temp_file, format="json", dry_run=True)

            # Verify database is still empty
            assert not KnowledgeBaseDocument.objects.exists()
            assert not KnowledgeBaseCategory.objects.exists()

        finally:
            Path(temp_file).unlink(missing_ok=True)

    @pytest.fixture
    def time_sensitive_data(self):
        """Create test data with specific timestamps for testing date filtering"""

        # Define timestamps
        old_time = datetime(2025, 9, 1, 12, 0, 0, tzinfo=timezone.utc)  # September 1st
        recent_time = datetime(
            2025, 9, 10, 12, 0, 0, tzinfo=timezone.utc
        )  # September 10th
        filter_time = datetime(
            2025, 9, 5, 12, 0, 0, tzinfo=timezone.utc
        )  # September 5th (between old and recent)

        # Create category
        category = KnowledgeBaseCategory.objects.create(
            name="Time Test Category", description="Test category for time filtering"
        )

        # Create old document and chunk (should be excluded)
        with freeze_time(old_time):
            old_document = KnowledgeBaseDocument.objects.create(
                title="Old Document",
                slug="old-doc",
                raw_content="Old content",
                content="Old content",
                category=category,
                status=KnowledgeBaseDocument.Status.READY,
            )

            old_chunk = KnowledgeBaseChunk.objects.create(
                source_document=old_document,
                content="Old chunk content",
                index=0,
                embedding=[1.0, 0.0, 0.0],
                metadata={"test": "old"},
            )

        # Create recent document and chunk (should be included)
        with freeze_time(recent_time):
            recent_document = KnowledgeBaseDocument.objects.create(
                title="Recent Document",
                slug="recent-doc",
                raw_content="Recent content",
                content="Recent content",
                category=category,
                status=KnowledgeBaseDocument.Status.READY,
            )

            recent_chunk = KnowledgeBaseChunk.objects.create(
                source_document=recent_document,
                content="Recent chunk content",
                index=0,
                embedding=[0.0, 1.0, 0.0],
                metadata={"test": "recent"},
            )

        # Create document with old timestamp but recent chunk (should be included)
        with freeze_time(old_time):
            mixed_document = KnowledgeBaseDocument.objects.create(
                title="Mixed Document",
                slug="mixed-doc",
                raw_content="Mixed content",
                content="Mixed content",
                category=category,
                status=KnowledgeBaseDocument.Status.READY,
            )

        # Create chunk with recent timestamp for mixed document
        with freeze_time(recent_time):
            mixed_chunk = KnowledgeBaseChunk.objects.create(
                source_document=mixed_document,
                content="Mixed chunk content",
                index=0,
                embedding=[0.0, 0.0, 1.0],
                metadata={"test": "mixed"},
            )

        return {
            "category": category,
            "old_document": old_document,
            "old_chunk": old_chunk,
            "recent_document": recent_document,
            "recent_chunk": recent_chunk,
            "mixed_document": mixed_document,
            "mixed_chunk": mixed_chunk,
            "old_time": old_time,
            "recent_time": recent_time,
            "filter_time": filter_time,
        }

    @patch(
        "baserow_enterprise.assistant.capabilities.knowledge_retrieval.handler.VectorStore"
    )
    def test_dump_with_updated_after_filter(
        self, mock_vector_store, time_sensitive_data
    ):
        """Test dump_knowledge_base with --updated-after filter"""

        mock_vector_store.return_value = TestVectorStore()

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_file = f.name

        try:
            filter_time = time_sensitive_data["filter_time"]

            # Test with datetime format
            datetime_str = filter_time.strftime("%Y-%m-%d %H:%M:%S")
            call_command(
                "dump_knowledge_base",
                temp_file,
                format="json",
                updated_after=datetime_str,
            )

            # Load and verify the dumped data
            with open(temp_file, "r") as f:
                data = json.load(f)

            # Extract document slugs from the dump
            document_slugs = []
            for item in data:
                if item["model"] == "baserow_enterprise.knowledgebasedocument":
                    document_slugs.append(item["fields"]["slug"])

            # Should include recent_document and mixed_document, but not old_document
            assert "recent-doc" in document_slugs, "Recent document should be included"
            assert (
                "mixed-doc" in document_slugs
            ), "Mixed document should be included (has recent chunk)"
            assert "old-doc" not in document_slugs, "Old document should be excluded"

            # Test with date-only format
            date_str = filter_time.strftime("%Y-%m-%d")
            call_command(
                "dump_knowledge_base", temp_file, format="json", updated_after=date_str
            )

            # Verify same results with date format
            with open(temp_file, "r") as f:
                data = json.load(f)

            document_slugs = []
            for item in data:
                if item["model"] == "baserow_enterprise.knowledgebasedocument":
                    document_slugs.append(item["fields"]["slug"])

            assert "recent-doc" in document_slugs
            assert "mixed-doc" in document_slugs
            assert "old-doc" not in document_slugs

        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_dump_with_updated_after_invalid_date_format(self):
        """Test dump_knowledge_base with invalid date format"""

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_file = f.name

        try:
            # Test with invalid date format
            with pytest.raises(Exception) as exc_info:
                call_command(
                    "dump_knowledge_base",
                    temp_file,
                    format="json",
                    updated_after="invalid-date-format",
                )

            # Should raise CommandError with helpful message
            assert "Invalid date format" in str(exc_info.value)

        finally:
            Path(temp_file).unlink(missing_ok=True)

    @patch(
        "baserow_enterprise.assistant.capabilities.knowledge_retrieval.handler.VectorStore"
    )
    def test_dump_with_updated_after_no_matches(
        self, mock_vector_store, time_sensitive_data
    ):
        """Test dump_knowledge_base when no documents match the date filter"""

        mock_vector_store.return_value = TestVectorStore()

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_file = f.name

        try:
            # Use a future date that should match no documents (after September 10th)
            future_time = datetime(2025, 9, 15, 12, 0, 0, tzinfo=timezone.utc)
            future_str = future_time.strftime("%Y-%m-%d %H:%M:%S")

            # Should raise CommandError when no documents match
            with pytest.raises(Exception) as exc_info:
                call_command(
                    "dump_knowledge_base",
                    temp_file,
                    format="json",
                    updated_after=future_str,
                )

            assert "No documents found that were updated after" in str(exc_info.value)

        finally:
            Path(temp_file).unlink(missing_ok=True)
