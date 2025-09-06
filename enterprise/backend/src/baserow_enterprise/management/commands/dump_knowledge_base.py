import bz2
import gzip
import zipfile
from pathlib import Path
from typing import Literal

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Exists, OuterRef, Q, QuerySet
from django.utils.dateparse import parse_date, parse_datetime

from baserow_enterprise.assistant.capabilities.knowledge_retrieval.handler import (
    KnowledgeBaseHandler,
)
from baserow_enterprise.assistant.models import (
    KnowledgeBaseChunk,
    KnowledgeBaseDocument,
)


class Command(BaseCommand):
    help = "Dump the knowledge base to a file with optional compression"

    def add_arguments(self, parser):
        parser.add_argument(
            "filename",
            type=str,
            help="Output filename for the knowledge base dump",
        )
        parser.add_argument(
            "--format",
            choices=["json", "xml", "yaml", "jsonl"],
            default="json",
            help="Serialization format (default: json)",
        )
        parser.add_argument(
            "--updated-after",
            type=str,
            help="Only dump documents updated after this date (ISO format: YYYY-MM-DD or YYYY-MM-DD HH:MM:SS). "
            "Includes documents where the document itself or any of its chunks were updated after this date.",
        )
        parser.add_argument(
            "--documents",
            nargs="*",
            help="Specific document slugs to dump (default: all documents)",
        )

    def _parse_date(self, date_str: str):
        """Parse a date string in ISO format."""

        if not date_str:
            return None

        # Try parsing as datetime first (with time component)
        parsed_datetime = parse_datetime(date_str)
        if parsed_datetime:
            return parsed_datetime

        # Try parsing as date only
        parsed_date = parse_date(date_str)
        if parsed_date:
            # Convert date to datetime at start of day
            from datetime import datetime, time

            from django.utils import timezone

            return timezone.make_aware(datetime.combine(parsed_date, time.min))

        raise CommandError(
            f"Invalid date format: '{date_str}'. "
            "Please use ISO format: YYYY-MM-DD or YYYY-MM-DD HH:MM:SS"
        )

    def handle(self, *args, **options):
        filename = options["filename"]
        format_type: Literal["json", "xml", "yaml", "jsonl"] = options["format"]
        document_slugs = options.get("documents")
        updated_after_str = options.get("updated_after")

        try:
            file_path = Path(filename)
            handler = KnowledgeBaseHandler()

            # Parse the updated_after date if provided
            updated_after_date = None
            if updated_after_str:
                updated_after_date = self._parse_date(updated_after_str)
                self.stdout.write(
                    f"Filtering documents updated after: {updated_after_date}"
                )

            # Start with all documents
            documents = KnowledgeBaseDocument.objects.select_related("category")

            # Apply slug filtering if specific slugs provided
            if document_slugs:
                documents = documents.filter(slug__in=document_slugs)

                if not documents.exists():
                    raise CommandError(
                        f"No documents found with slugs: {', '.join(document_slugs)}"
                    )

            # Apply date filtering if updated_after is provided
            if updated_after_date:
                # Create subquery to check if any chunk was updated after the date
                updated_chunks = KnowledgeBaseChunk.objects.filter(
                    source_document=OuterRef("pk"), updated_on__gt=updated_after_date
                )

                # Filter documents where either the document OR any of its chunks
                # were updated after the specified date
                documents = documents.filter(
                    Q(updated_on__gt=updated_after_date) | Q(Exists(updated_chunks))
                )

            # Check if we have any documents to dump
            if not documents.exists():
                if updated_after_date and document_slugs:
                    raise CommandError(
                        f"No documents found with slugs {', '.join(document_slugs)} "
                        f"that were updated after {updated_after_date}"
                    )
                elif updated_after_date:
                    raise CommandError(
                        f"No documents found that were updated after {updated_after_date}"
                    )
                elif document_slugs:
                    raise CommandError(
                        f"No documents found with slugs: {', '.join(document_slugs)}"
                    )
                else:
                    raise CommandError("No documents found in the knowledge base")

            # Display what we're dumping
            if document_slugs and updated_after_date:
                self.stdout.write(
                    f"Found {documents.count()} documents matching slugs "
                    f"{', '.join(document_slugs)} updated after {updated_after_date}: "
                    f"{', '.join(doc.slug for doc in documents)}"
                )
            elif document_slugs:
                self.stdout.write(
                    f"Found {documents.count()} documents to dump: "
                    f"{', '.join(doc.slug for doc in documents)}"
                )
            elif updated_after_date:
                self.stdout.write(
                    f"Found {documents.count()} documents updated after {updated_after_date}"
                )
            else:
                self.stdout.write("Dumping all documents in the knowledge base")

            # Determine if we need compression based on file extension
            file_extension = file_path.suffix.lower()

            if file_extension == ".gz":
                self._dump_with_gzip(handler, file_path, format_type, documents)
            elif file_extension == ".bz2":
                self._dump_with_bzip2(handler, file_path, format_type, documents)
            elif file_extension == ".zip":
                self._dump_with_zip(handler, file_path, format_type, documents)
            else:
                # No compression, write directly to file
                self._dump_to_file(handler, file_path, format_type, documents)

            self.stdout.write(
                self.style.SUCCESS(f"Successfully dumped knowledge base to {filename}")
            )

        except Exception as e:
            raise CommandError(f"Failed to dump knowledge base: {str(e)}")

    def _dump_to_file(
        self,
        handler: KnowledgeBaseHandler,
        file_path: str,
        format_type: str,
        documents: QuerySet[KnowledgeBaseDocument] | None,
    ):
        with open(file_path, "w", encoding="utf-8") as f:
            handler.dump_knowledge_base(
                documents=documents, format=format_type, stream=f
            )

    def _dump_with_gzip(
        self,
        handler: KnowledgeBaseHandler,
        file_path: str,
        format_type: str,
        documents: QuerySet[KnowledgeBaseDocument] | None,
    ):
        with gzip.open(file_path, "wt", encoding="utf-8") as f:
            handler.dump_knowledge_base(
                documents=documents, format=format_type, stream=f
            )

    def _dump_with_bzip2(
        self,
        handler: KnowledgeBaseHandler,
        file_path: str,
        format_type: str,
        documents: QuerySet[KnowledgeBaseDocument] | None,
    ):
        with bz2.open(file_path, "wt", encoding="utf-8") as f:
            handler.dump_knowledge_base(
                documents=documents, format=format_type, stream=f
            )

    def _dump_with_zip(
        self,
        handler: KnowledgeBaseHandler,
        file_path: str,
        format_type: str,
        documents: QuerySet[KnowledgeBaseDocument] | None,
    ):
        # For zip files, we need to create a file inside the archive
        data_filename = f"knowledge_base.{format_type}"

        with zipfile.ZipFile(file_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Get the serialized data as string
            serialized_data = handler.dump_knowledge_base(
                documents=documents, format=format_type
            )

            # Write to zip file
            zf.writestr(data_filename, serialized_data)
