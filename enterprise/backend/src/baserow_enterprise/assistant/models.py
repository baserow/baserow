from typing import NamedTuple
import uuid

from django.contrib.auth import get_user_model
from django.db import models
from django.db.models.signals import post_migrate, pre_delete
from django.contrib.postgres.fields import ArrayField

from baserow.core.mixins import BigAutoFieldMixin, CreatedAndUpdatedOnMixin
from baserow.core.models import Workspace

User = get_user_model()


class AssistantChat(BigAutoFieldMixin, CreatedAndUpdatedOnMixin, models.Model):
    """
    Model representing a chat with the AI assistant.
    """

    TITLE_MAX_LENGTH = 250

    class Status(models.TextChoices):
        IDLE = "idle", "Idle"
        IN_PROGRESS = "in_progress", "In progress"
        CANCELING = "canceling", "Canceling"
        INTERRUPTED = "interrupted", "Interrupted"
        ERROR = "error", "Error"

    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        help_text="Unique identifier for the chat. Can be provided by the client.",
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, help_text="The user who owns the chat."
    )
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        help_text="The workspace the chat belongs to.",
    )
    title = models.CharField(
        max_length=TITLE_MAX_LENGTH, blank=True, help_text="The title of the chat."
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.IDLE
    )

    class Meta:
        indexes = [
            models.Index(fields=["user", "workspace", "-updated_on"]),
        ]

    def __str__(self):
        return f"Chat: {self.title} ({self.user_id})"


class DocumentCategory(NamedTuple):
    name: str
    parent: str


# More categories can be added to the model, but these are the defaults ones.
DEFAULT_CATEGORIES = [
    # Workspace
    DocumentCategory("workspace", None),
    DocumentCategory("snapshot", "workspace"),
    DocumentCategory("roles and permissions", "workspace"),
    # Database
    DocumentCategory("database", "workspace"),
    DocumentCategory("table", "database"),
    DocumentCategory("field", "table"),
    DocumentCategory("view", "table"),
    DocumentCategory("row", "table"),
    DocumentCategory("database formula", "table"),
    # Application Builder
    DocumentCategory("application builder", "workspace"),
    DocumentCategory("element", "application builder"),
    DocumentCategory("data source", "application builder"),
    DocumentCategory("page", "application builder"),
    DocumentCategory("builder formula", "application builder"),
    # Automation
    DocumentCategory("automation", "workspace"),
    DocumentCategory("workflow", "automation"),
    DocumentCategory("node", "workflow"),
    # Dashboard
    DocumentCategory("dashboard", "workspace"),
    DocumentCategory("widget", "dashboard"),
    #
    DocumentCategory("collaboration", None),
    DocumentCategory("integrations", None),
    DocumentCategory("mcp", None),
    DocumentCategory("getting started", None),
    DocumentCategory("hosting", None),
    DocumentCategory("account management", None),
    # Plans
    DocumentCategory("billing", None),
    DocumentCategory("premium", "billing"),
    DocumentCategory("advanced", "billing"),
    DocumentCategory("enterprise", "billing"),
    #
    DocumentCategory("sso", "enterprise"),
]


class KnowledgeBaseDocumentCategory(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        help_text="The parent document category, if any.",
    )

    @property
    def full_path(self) -> str:
        """
        Get the full path of the category, including all parent categories.
        """

        if self.parent:
            return f"{self.parent.full_path} > {self.name}"
        return self.name

    def __str__(self):
        return self.name


class KnowledgeBaseDocument(CreatedAndUpdatedOnMixin, models.Model):
    """
    Model representing a document in the Assistant knowledge base. The IngestionStatus
    defines the state of the document, from when it's created to when it's fully
    processed and ready for use to the assistant.
    """

    TITLE_MAX_LENGTH = 250

    class Status(models.TextChoices):
        NEW = "new", "New"  # never ingested
        PROCESSING = "processing", "Processing"  # any step running
        READY = "ready", "Ready"  # fully indexed and retrievable
        STALE_CONTENT = (
            "stale_content",
            "Stale content",
        )  # source changed (checksum/version differ) needs re-ingest
        ERROR = "error", "Error"  # last run failed (any step).
        DISABLED = "disabled", "Disabled"  # excluded from retrieval.

    class DocumentType(models.TextChoices):
        RAW_DOCUMENT = "raw_document", "Raw Document"
        """
        Raw document where the content is manually provided in `raw_content`, without a
        source_url.
        """
        BASEROW_USER_DOCS = "baserow_user_docs", "Baserow User Docs"
        """
        Documents downloaded from `baserow.io/user-docs`, our online Knowledge Base.
        """
        FAQ = "faq", "FAQ"
        """
        Frequently Asked Question. It could be a single question or multiple ones for
        the same topic.
        """
        TEMPLATE = "template", "Template"
        """
        A document that contains a template example for a specific use case.
        """

    title = models.CharField(
        max_length=TITLE_MAX_LENGTH, help_text="The title of the document."
    )
    source_url = models.URLField(
        blank=True, help_text="The source URL of the document, if applicable."
    )
    type = models.CharField(
        max_length=20, choices=DocumentType.choices, default=DocumentType.RAW_DOCUMENT
    )
    raw_content = models.TextField(
        help_text=(
            "The raw content of the document, before any processing. "
            "This field can be automatically populated by the source_url or set manually."
        )
    )
    process_document = models.BooleanField(
        default=True,
        help_text="Whether to process the document for ingestion or use the raw_content as-is.",
    )
    content = models.TextField(
        help_text="The processed content of the document, ready for use by the AI assistant."
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    category = models.ForeignKey(
        KnowledgeBaseDocumentCategory,
        on_delete=models.CASCADE,
        related_name="documents",
        help_text=(
            "The category this document belongs to. "
            "Every document should belong to exactly one category. "
            "If not, split it in multiple documents first."
        ),
    )

    def __str__(self):
        return f"Document: {self.title}"


class KnowledgeBaseDocumentChunk(CreatedAndUpdatedOnMixin, models.Model):
    source_document = models.ForeignKey(
        KnowledgeBaseDocument,
        on_delete=models.CASCADE,
        related_name="chunks",
        help_text="The document this chunk belongs to.",
    )
    vector_id = models.CharField(
        null=True,
        max_length=255,
        help_text="The vector ID used in the vector store of the chunk.",
    )
    embedding = ArrayField(
        models.FloatField(),
        help_text=(
            "The embedding vector for the chunk. This won't be used to retrieve the chunk. "
            "It's only a backup copy of the one used in the vector store, in case redis is cleared."
        ),
        default=list,
    )
    index = models.PositiveIntegerField(
        help_text="The chunk index within the document."
    )
    content = models.TextField(help_text="The content of the chunk.")
    metadata = models.JSONField(help_text="Additional metadata about the chunk.")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["vector_id"],
                condition=(~models.Q(vector_id__isnull=True)),
                name="unique_vector_id_constraint",
            )
        ]

    def __str__(self):
        return f"Doc {self.source_document_id} - chunk {self.index} "


def cleanup_document_vector_chunks(sender, instance: "KnowledgeBaseDocument", **kwargs):
    """
    Before deleting a KnowledgeBaseDocument, clean up all related vector chunks
    from the RedisVectorStore to prevent orphaned vectors.
    """
    from .graph.doc_search.handler import RedisVectorStore

    try:
        # Get all chunks for this document that have vector_ids
        chunks_with_vectors = instance.chunks.filter(vector_id__isnull=False)
        vector_ids = [
            chunk.vector_id for chunk in chunks_with_vectors if chunk.vector_id
        ]

        if vector_ids:
            # Initialize the vector store and delete the vectors
            vector_store = RedisVectorStore()
            vector_store.delete_many(vector_ids)

    except Exception as e:
        # Log the error but don't prevent the document deletion
        import logging

        logger = logging.getLogger(__name__)
        logger.error(
            f"Failed to cleanup vector chunks for document {instance.id}: {e}",
            exc_info=True,
        )


# Connect the signal handler
pre_delete.connect(cleanup_document_vector_chunks, sender=KnowledgeBaseDocument)


@post_migrate.connect
def create_default_knowledge_base_categories(sender, **kwargs):
    """
    Create default knowledge base categories if they don't exist. They're needed as
    document type importers rely on them.
    """

    category_by_name = {}
    categories = []
    starting_id = KnowledgeBaseDocumentCategory.objects.count() + 1
    for index, (name, parent_name) in enumerate(DEFAULT_CATEGORIES, start=starting_id):
        parent = category_by_name.get(parent_name)
        category = KnowledgeBaseDocumentCategory(
            id=index,
            name=name,
            parent_id=parent.id if parent else None,
        )
        categories.append(category)
        category_by_name[name] = category

    KnowledgeBaseDocumentCategory.objects.bulk_create(categories, ignore_conflicts=True)
