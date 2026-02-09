import uuid
from typing import Iterable, NamedTuple

from django.contrib.auth import get_user_model
from django.db import models

from baserow.core.mixins import BigAutoFieldMixin, CreatedAndUpdatedOnMixin
from baserow.core.models import Workspace
from baserow.core.pgvector import EmbeddingMixin

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


class AssistantChatMessage(BigAutoFieldMixin, CreatedAndUpdatedOnMixin, models.Model):
    """
    Model representing a message in an assistant chat.
    """

    class Role(models.TextChoices):
        HUMAN = "human", "Human"
        AI = "ai", "AI"

    chat = models.ForeignKey(
        AssistantChat,
        on_delete=models.CASCADE,
        related_name="messages",
        help_text="The chat this message belongs to.",
    )
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField(help_text="The content of the message.")
    artifacts = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "A JSON field to store any additional artifacts related to the message, "
            "such as metadata or processing results."
        ),
    )
    action_group_id = models.UUIDField(
        null=True,
        help_text=(
            "Unique identifier for the action group. Can be provided by the client. "
            "All the actions done to produce this message can be undone by referencing this ID."
        ),
    )

    class Meta:
        indexes = [
            models.Index(fields=["chat", "created_on"]),
        ]


class AssistantChatPrediction(
    BigAutoFieldMixin, CreatedAndUpdatedOnMixin, models.Model
):
    """
    Model representing a prediction for an assistant chat message, including the
    reasoning and any tool calls made by the AI. It also captures optional feedback from
    the human user regarding the prediction.
    """

    SENTIMENT_MAP = {
        "LIKE": 1,
        "DISLIKE": -1,
        # Add also the reverse mapping for convenience.
        1: "LIKE",
        -1: "DISLIKE",
    }

    human_message = models.OneToOneField(
        AssistantChatMessage,
        on_delete=models.CASCADE,
        related_name="+",
        help_text="The human message that caused this prediction.",
    )
    ai_response = models.OneToOneField(
        AssistantChatMessage,
        on_delete=models.CASCADE,
        related_name="prediction",
        help_text="The AI response message generated as a prediction.",
    )
    prediction = models.JSONField(
        default=dict,
        help_text="The prediction data, including the reasoning and any tool calls.",
    )
    human_sentiment = models.SmallIntegerField(
        choices=[
            (SENTIMENT_MAP["LIKE"], "Like"),
            (SENTIMENT_MAP["DISLIKE"], "Dislike"),
        ],
        null=True,
        help_text="Optional feedback provided by the human user on the prediction.",
    )
    human_feedback = models.TextField(
        blank=True,
        help_text="Optional feedback provided by the human user on the prediction.",
    )

    def get_human_sentiment_display(self):
        """
        Returns the display value of the human sentiment.
        """

        return self.SENTIMENT_MAP.get(self.human_sentiment)


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
    DocumentCategory("sso", None),
    # Plans
    DocumentCategory("billing", None),
    DocumentCategory("premium", "billing"),
    DocumentCategory("advanced", "billing"),
    DocumentCategory("enterprise", "billing"),
    # FAQ
    DocumentCategory("faq", None),
    # Dev Docs
    DocumentCategory("dev_docs", None),
]


class KnowledgeBaseDocumentCategoryManager(models.Manager):
    def get_by_natural_key(self, name):
        return self.get(name=name)


class KnowledgeBaseCategory(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        related_name="children",
        help_text="The parent document category, if any.",
    )

    objects = KnowledgeBaseDocumentCategoryManager()

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

    def natural_key(self):
        return (self.name,)


class KnowledgeBaseDocumentManager(models.Manager):
    def get_by_natural_key(self, slug):
        return self.get(slug=slug)


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
        BASEROW_DEV_DOCS = "baserow_dev_docs", "Baserow Dev Docs"
        """
        Documents downloaded from `baserow.io/docs`, the dev docs.
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
    slug = models.SlugField(
        max_length=255,
        unique=True,
        help_text=(
            "A unique slug identifier for the document, used for easy reference."
        ),
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
        KnowledgeBaseCategory,
        null=True,
        on_delete=models.CASCADE,
        related_name="documents",
        help_text=(
            "The category this document belongs to. "
            "Every document should belong to exactly one category. "
            "If not, split it in multiple documents first."
        ),
    )

    objects = KnowledgeBaseDocumentManager()

    def generate_slug(self, excludes: Iterable[str] | None = None) -> str:
        """
        Generate a slug from the title. This is used when creating a new document
        without a slug.
        """

        base_slug = self.title.lower().replace(" ", "-")
        slug = base_slug

        excludes = set(list(excludes or []))
        counter = 1

        while slug in excludes:
            slug = f"{base_slug}-{counter}"
            counter += 1

        self.slug = slug
        return slug

    def __str__(self):
        return f"Document: {self.title}"

    def natural_key(self):
        return (self.slug,)


class KnowledgeBaseChunkManager(models.Manager):
    def get_by_natural_key(self, document_slug, index):
        return self.get(source_document__slug=document_slug, index=index)


class KnowledgeBaseChunk(CreatedAndUpdatedOnMixin, EmbeddingMixin):
    """
    Model representing a chunk of a knowledge base document. Documents are split into
    smaller chunks to facilitate efficient retrieval and embedding generation. Every
    chunk belongs to a single document and has a unique index within that document,
    representing its position.
    """

    source_document = models.ForeignKey(
        KnowledgeBaseDocument,
        on_delete=models.CASCADE,
        related_name="chunks",
        help_text="The document this chunk belongs to.",
    )
    index = models.PositiveIntegerField(
        help_text=(
            "The index of this chunk within the document, representing its position "
            "in the original document."
        )
    )
    content = models.TextField(
        help_text=(
            "The portion of the original document content that this chunk represents."
        )
    )
    metadata = models.JSONField(
        help_text="Additional metadata about the chunk.", default=dict
    )
    # The embedding VectorField will be dynamically added if pgvector is available.

    objects = KnowledgeBaseChunkManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source_document", "index"],
                name="unique_document_index_constraint",
            ),
        ]

    def natural_key(self):
        return (self.source_document.slug, self.index)
