from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from loguru import logger

from baserow_enterprise.assistant.tools.search_docs.handler import KnowledgeBaseHandler


class Command(BaseCommand):
    help = "Load the knowledge base from a file with optional decompression"

    def add_arguments(self, parser):
        parser.add_argument(
            "filename",
            type=str,
            help="Input filename for the knowledge base dump to load. It must be a zip file.",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Clear the entire knowledge base before loading (default: False, only replace documents with same slug)",
        )

    def handle(self, *args, **options):
        filename = options["filename"]
        reset_kb = options["reset"]

        try:
            file_path = Path(filename)

            if not file_path.exists():
                raise CommandError(f"File does not exist: {filename}")

            handler = KnowledgeBaseHandler()
            # Clear knowledge base if reset is requested
            if reset_kb:
                self._clear_knowledge_base()
                self.stdout.write(self.style.WARNING("Cleared existing knowledge base"))

            # Load the knowledge base
            with transaction.atomic():
                loaded_docs = handler.load_knowledge_base(file_path)

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully loaded {len(loaded_docs)} documents from {filename}"
                    )
                )

                # Show loaded document details
                for doc in loaded_docs:
                    self.stdout.write(f"  - {doc.title} (slug: {doc.slug})")

        except Exception as e:
            logger.exception("Failed to load knowledge base")
            raise CommandError(f"Failed to load knowledge base: {str(e)}")

    def _clear_knowledge_base(self):
        from baserow_enterprise.assistant.models import (
            KnowledgeBaseCategory,
            KnowledgeBaseChunk,
            KnowledgeBaseDocument,
        )

        # Delete all documents (this will cascade to chunks)
        KnowledgeBaseChunk.objects.all().delete()
        documents_count, _ = KnowledgeBaseDocument.objects.all().delete()

        # Delete all categories
        categories_count = KnowledgeBaseCategory.objects.count()
        KnowledgeBaseCategory.objects.all().delete()

        self.stdout.write(
            f"Deleted {documents_count} documents and {categories_count} categories"
        )
