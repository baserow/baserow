import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from loguru import logger

from baserow_enterprise.assistant.models import KnowledgeBaseDocument
from baserow_enterprise.assistant.tools.search_docs.handler import KnowledgeBaseHandler


class Command(BaseCommand):
    help = (
        "Dump the knowledge base to a file with optional compression. "
        "By default, only documents in READY status are dumped, since they are the only ones "
        "used for retrieval."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "filename",
            type=str,
            help="Output filename for the knowledge base dump. It will be saved as a zip file.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force overwrite of the output file if it already exists.",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Dump all documents, including those not in READY status (default: False, only dump READY documents)",
        )

    def handle(self, *args, **options):
        filename = options["filename"]
        force_overwrite = options["force"]
        dump_all = options["all"]

        try:
            file_path = Path(filename)
            if os.path.exists(file_path) and not force_overwrite:
                self.stdout.write(
                    "Operation cancelled. File already exists. Use --force to overwrite."
                )
                return

            handler = KnowledgeBaseHandler()
            document_filters = (
                None if dump_all else Q(status=KnowledgeBaseDocument.Status.READY)
            )
            document_count = handler.dump_knowledge_base(
                file_path, document_filters=document_filters
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully dumped {document_count} documents to {filename}"
                )
            )

        except Exception as e:
            logger.exception("Failed to dump knowledge base")
            raise CommandError(f"Failed to dump knowledge base: {str(e)}")
