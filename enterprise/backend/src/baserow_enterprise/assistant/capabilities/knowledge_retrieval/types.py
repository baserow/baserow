from typing import Any, TypedDict

from pydantic import BaseModel, Field

from .constants import (
    DOCUMENT_CHUNK_ID_FIELD_NAME,
    DOCUMENT_CONTENT_FIELD_NAME,
    EMBEDDING_DIMENSIONS,
    KNOWLEDGE_EMBEDDING_FIELD_NAME,
    KNOWLEDGE_INDEX_NAME,
)


class KnowledgeToolArgsSchema(BaseModel):
    query: str = Field(
        description=(
            "A reformulated English version of the user's question that incorporates relevant context and details."
        )
    )


class KnowledgeToolArtifact(BaseModel):
    knowledge: str = Field(
        description="The comprehensive answer generated, preserving all relevant details."
    )
    sources: list[str] = Field(
        description=(
            "The list of relevant source URLs referenced in the knowledge. "
            "Limit to the 5 most relevant, in order of relevance."
        ),
        default_factory=list,
    )


class KnowledgeVector(TypedDict):
    title: str
    content: str
    section: str
    document_chunk_id: int
    category: str
    embedding: list[float]
    url: str

    @staticmethod
    def to_redis_schema() -> list[dict[str, Any]]:
        return [
            {"name": "title", "type": "text"},
            {"name": "url", "type": "text"},
            {"name": DOCUMENT_CONTENT_FIELD_NAME, "type": "text"},
            {"name": "section", "type": "text"},
            {"name": DOCUMENT_CHUNK_ID_FIELD_NAME, "type": "numeric"},
            {"name": "category", "type": "tag"},
            {
                "name": KNOWLEDGE_EMBEDDING_FIELD_NAME,
                "type": "vector",
                "attrs": {
                    "dims": EMBEDDING_DIMENSIONS,
                    "distance_metric": "cosine",
                    "algorithm": "flat",
                    "datatype": "float32",
                },
            },
        ]


KNOWLEDGE_INDEX_SCHEMA = {
    "index": {
        "name": KNOWLEDGE_INDEX_NAME,
        "prefix": "aikb",
    },
    "fields": KnowledgeVector.to_redis_schema(),
}
