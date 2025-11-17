from django.core.management.base import BaseCommand

from baserow_enterprise.assistant.tools.search_user_docs.handler import (
    KnowledgeBaseHandler,
)


class Command(BaseCommand):
    help = (
        "Sync the knowledge base with the latest data from the website_export.csv "
        "file in the repository."
    )

    def handle(self, *args, **options):
        handler = KnowledgeBaseHandler()

        if handler.can_have_knowledge_base():
            handler.sync_knowledge_base()
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"This instance does not have the `BASEROW_EMBEDDINGS_API_URL` "
                    f"environment variable configured or the PostgreSQL server does "
                    f"not have the pgvector extension."
                )
            )
