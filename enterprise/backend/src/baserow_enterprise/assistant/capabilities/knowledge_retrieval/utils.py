from array import array

from baserow_enterprise.assistant.models import KnowledgeBaseChunk

from .types import KnowledgeVector


def document_chunk_to_knowledge_vector(
    document_chunk: KnowledgeBaseChunk,
) -> KnowledgeVector:
    """
    Converts a KnowledgeBaseDocumentChunk instance to a KnowledgeVector dictionary,
    ready for insertion into the vector store.

    :param document_chunk: The KnowledgeBaseDocumentChunk instance to convert.
    :return: A KnowledgeVector dictionary representing the document chunk.
    """

    source_doc = document_chunk.source_document

    # Prepare the embedding as a byte array for Redis
    embedding = array(
        "f",  # 'f' is the type code for float32
        list(document_chunk.embedding) if document_chunk.embedding else [],
    ).tobytes()

    return KnowledgeVector(
        title=source_doc.title,
        section=document_chunk.metadata.get("section", ""),
        category=source_doc.category.full_path if source_doc.category else "",
        url=source_doc.source_url or "",
        content=document_chunk.content,
        embedding=embedding,
        document_chunk_id=document_chunk.id,
    )
