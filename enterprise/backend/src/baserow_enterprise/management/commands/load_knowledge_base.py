import bz2
import gzip
import zipfile
from pathlib import Path
from typing import Literal, TextIO

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from baserow_enterprise.assistant.capabilities.knowledge_retrieval.handler import (
    KnowledgeBaseHandler,
)


class Command(BaseCommand):
    help = "Load the knowledge base from a file with optional decompression"

    def add_arguments(self, parser):
        parser.add_argument(
            "filename",
            type=str,
            help="Input filename for the knowledge base dump to load",
        )
        parser.add_argument(
            "--format",
            choices=["json", "xml", "yaml", "jsonl"],
            default="json",
            help="Serialization format (default: json)",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Clear the entire knowledge base before loading (default: False, only replace documents with same slug)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be imported without actually importing",
        )

    def handle(self, *args, **options):
        filename = options["filename"]
        format_type: Literal["json", "xml", "yaml", "jsonl"] = options["format"]
        reset_kb = options["reset"]
        dry_run = options["dry_run"]

        try:
            file_path = Path(filename)

            if not file_path.exists():
                raise CommandError(f"File does not exist: {filename}")

            handler = KnowledgeBaseHandler()

            # Determine if we need decompression based on file extension
            file_extension = file_path.suffix.lower()

            if file_extension == ".gz":
                # Handle gzip decompression
                stream_or_string = self._load_from_gzip(file_path)
            elif file_extension == ".bz2":
                # Handle bzip2 decompression
                stream_or_string = self._load_from_bzip2(file_path)
            elif file_extension == ".zip":
                # Handle zip decompression
                stream_or_string = self._load_from_zip(file_path, format_type)
            else:
                # No compression, read directly from file
                stream_or_string = self._load_from_file(file_path)

            # Preview the data if dry run
            if dry_run:
                self._preview_import(stream_or_string, format_type)
                return

            # Clear knowledge base if reset is requested
            if reset_kb:
                self._clear_knowledge_base()
                self.stdout.write(self.style.WARNING("Cleared existing knowledge base"))

            # Load the knowledge base
            with transaction.atomic():
                loaded_docs = handler.load_knowledge_base(
                    stream_or_string=stream_or_string, format=format_type
                )

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully loaded {len(loaded_docs)} documents from {filename}"
                    )
                )

                # Show loaded document details
                for doc in loaded_docs:
                    self.stdout.write(f"  - {doc.title} (slug: {doc.slug})")

        except Exception as e:
            raise CommandError(f"Failed to load knowledge base: {str(e)}")

    def _load_from_file(self, file_path: Path) -> TextIO:
        return open(file_path, "r", encoding="utf-8")

    def _load_from_gzip(self, file_path: Path) -> TextIO:
        return gzip.open(file_path, "rt", encoding="utf-8")

    def _load_from_bzip2(self, file_path: Path) -> TextIO:
        return bz2.open(file_path, "rt", encoding="utf-8")

    def _load_from_zip(self, file_path: Path, format_type: str) -> str:
        with zipfile.ZipFile(file_path, "r") as zf:
            # Look for a file with the expected format extension
            data_filename = f"knowledge_base.{format_type}"

            # Try to find the exact filename first
            if data_filename in zf.namelist():
                with zf.open(data_filename) as f:
                    return f.read().decode("utf-8")

            # If not found, try to find any file with the format extension
            matching_files = [
                name for name in zf.namelist() if name.endswith(f".{format_type}")
            ]

            if matching_files:
                with zf.open(matching_files[0]) as f:
                    return f.read().decode("utf-8")

            # If no matching files, try the first file in the archive
            if zf.namelist():
                with zf.open(zf.namelist()[0]) as f:
                    return f.read().decode("utf-8")

            raise CommandError("No files found in the zip archive")

    def _clear_knowledge_base(self):
        from baserow_enterprise.assistant.models import (
            KnowledgeBaseCategory,
            KnowledgeBaseDocument,
        )

        # Delete all documents (this will cascade to chunks)
        documents_count = KnowledgeBaseDocument.objects.count()
        KnowledgeBaseDocument.objects.all().delete()

        # Delete all categories
        categories_count = KnowledgeBaseCategory.objects.count()
        KnowledgeBaseCategory.objects.all().delete()

        self.stdout.write(
            f"Deleted {documents_count} documents and {categories_count} categories"
        )

    def _preview_import(self, stream_or_string, format_type: str):
        """Preview what would be imported without actually importing"""

        from django.core import serializers

        self.stdout.write(self.style.WARNING("DRY RUN - Preview of import:"))

        try:
            # Parse the data to see what would be imported
            objects = list(serializers.deserialize(format_type, stream_or_string))

            documents = []
            categories = []
            chunks = []

            for obj in objects:
                obj_type = obj.object.__class__.__name__
                if obj_type == "KnowledgeBaseDocument":
                    documents.append(obj.object)
                elif obj_type == "KnowledgeBaseCategory":
                    categories.append(obj.object)
                elif obj_type == "KnowledgeBaseChunk":
                    chunks.append(obj.object)

            self.stdout.write(f"Categories to import: {len(categories)}")
            for cat in categories:
                parent_info = f" (parent: {cat.parent.name})" if cat.parent else ""
                self.stdout.write(f"  - {cat.name}{parent_info}")

            self.stdout.write(f"Documents to import: {len(documents)}")
            for doc in documents:
                category_info = (
                    f" (category: {doc.category.name})" if doc.category else ""
                )
                self.stdout.write(f"  - {doc.title} (slug: {doc.slug}){category_info}")

            self.stdout.write(f"Chunks to import: {len(chunks)}")

            # Check for conflicts with existing documents
            if documents:
                from baserow_enterprise.assistant.models import KnowledgeBaseDocument

                existing_slugs = set(
                    KnowledgeBaseDocument.objects.filter(
                        slug__in=[doc.slug for doc in documents]
                    ).values_list("slug", flat=True)
                )

                if existing_slugs:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Documents that would be replaced: {', '.join(existing_slugs)}"
                        )
                    )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to preview import: {str(e)}"))
