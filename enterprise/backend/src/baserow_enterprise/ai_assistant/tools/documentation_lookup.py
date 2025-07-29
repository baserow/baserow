import re
import os
import asyncio
from typing import List, Dict, Optional, Tuple
from pathlib import Path

import numpy as np
from langchain_core.tools import BaseTool
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field
from langchain_openai import OpenAIEmbeddings
from asgiref.sync import sync_to_async
from langgraph.prebuilt import create_react_agent


class DocumentationLookupArgs(BaseModel):
    """Arguments for documentation lookup."""

    query: str = Field(
        description="The query to search for in the Baserow documentation"
    )
    context: Optional[str] = Field(
        default=None,
        description="Optional context to filter results (e.g. 'database', 'application-builder', 'fields', 'views')",
    )
    k: int = Field(
        default=3,
        description="Number of most relevant documentation sections to return",
    )


class DocumentationResult(BaseModel):
    """Result from documentation lookup."""

    content: str
    source_file: str
    similarity: float


class DocumentationLookupArtifact(BaseModel):
    """Artifact containing documentation lookup results."""

    results: List[DocumentationResult]
    query: str


class VectorStoreRetriever:
    """Vector store for documentation retrieval using embeddings."""

    def __init__(self, docs: List[Dict], vectors: List, embeddings_model):
        self._arr = np.array(vectors)
        self._docs = docs
        self._embeddings_model = embeddings_model

    @classmethod
    def from_docs(cls, docs: List[Dict], embeddings_model):
        """Create retriever from documents."""
        texts = [doc["page_content"] for doc in docs]
        embeddings = embeddings_model.embed_documents(texts)
        return cls(docs, embeddings, embeddings_model)

    def query(
        self, query: str, k: int = 5, context_filter: Optional[str] = None
    ) -> List[Dict]:
        """Query the vector store for similar documents."""
        query_embedding = self._embeddings_model.embed_query(query)

        # Calculate cosine similarity
        scores = np.array(query_embedding) @ self._arr.T

        # Filter by context if provided
        if context_filter:
            filtered_indices = []
            for idx, doc in enumerate(self._docs):
                category = doc.get("metadata", {}).get("category", "")
                file_path = doc.get("source_file", "")

                # Context filtering logic
                if self._matches_context(context_filter, category, file_path):
                    filtered_indices.append(idx)

            # Only consider scores for filtered documents
            filtered_scores = [(idx, scores[idx]) for idx in filtered_indices]
            filtered_scores.sort(key=lambda x: x[1], reverse=True)

            # Take top k from filtered results
            top_k_filtered = filtered_scores[:k]

            return [
                {**self._docs[idx], "similarity": float(score)}
                for idx, score in top_k_filtered
            ]
        else:
            # Get top k indices (original logic)
            top_k_idx = np.argpartition(scores, -k)[-k:]
            top_k_idx_sorted = top_k_idx[np.argsort(-scores[top_k_idx])]

            return [
                {**self._docs[idx], "similarity": float(scores[idx])}
                for idx in top_k_idx_sorted
            ]

    def _matches_context(
        self, context_filter: str, category: str, file_path: str
    ) -> bool:
        """Check if document matches the context filter."""
        context_lower = context_filter.lower()
        category_lower = category.lower()
        file_path_lower = file_path.lower()

        # Define context mappings
        context_mappings = {
            "database": [
                "database",
                "tables",
                "fields",
                "field-types",
                "rows",
                "views",
                "view-types",
            ],
            "application-builder": ["app-builder"],
            "fields": ["fields", "field-types"],
            "field-types": ["field-types"],
            "formulas": ["formulas", "fields"],
            "views": ["views", "view-types"],
            "security": ["security", "collaboration"],
            "integrations": ["integrations", "api"],
            "enterprise": ["enterprise", "admin", "sso"],
            "workspace": ["workspace"],
        }

        # Check direct matches
        if context_lower == category_lower:
            return True

        # Check context mapping matches
        if context_lower in context_mappings:
            return category_lower in context_mappings[context_lower]

        # Check if context appears in file path
        if context_lower in file_path_lower:
            return True

        return False


# Global cache outside of the Pydantic model to avoid attribute conflicts
_GLOBAL_RETRIEVER_CACHE: Optional[VectorStoreRetriever] = None
_GLOBAL_DOCS_LOADED: bool = False
_GLOBAL_INITIALIZATION_LOCK = asyncio.Lock()


class DocumentationLookupTool(BaseTool):
    """Tool to search Baserow documentation for relevant information."""

    name: str = "documentation_lookup"
    description: str = (
        "Search the Baserow documentation to find information about features, "
        "concepts, API usage, permissions, and how to use Baserow. "
        "Use this tool when users ask about Baserow functionality, features, "
        "or need help understanding how to do something in Baserow. "
        "IMPORTANT: Use context parameter to improve accuracy:\n"
        "- 'database' or 'fields' for table field types (Number, Text, Date, etc.)\n"
        "- 'application-builder' for app builder elements (Button, Form, etc.)\n"
        "- 'views' for view types (Grid, Gallery, Kanban, etc.)\n"
        "- 'security' for permissions and roles\n"
        "- 'integrations' for API and third-party tools"
    )
    args_schema: type = DocumentationLookupArgs
    response_format: str = "content_and_artifact"

    def _load_documentation(self) -> List[Dict]:
        """Load all documentation files from the docs directory."""
        docs = []
        base_path = Path(__file__).parent.parent / "docs"

        if not base_path.exists():
            return docs

        # Walk through all markdown files in the docs directory
        for md_file in base_path.rglob("*.md"):
            try:
                with open(md_file, "r", encoding="utf-8") as f:
                    content = f.read()

                # Split content into sections based on headers
                sections = re.split(r"(?=\n##\s)", content)

                for section in sections:
                    if section.strip():
                        # Get relative path for source tracking
                        relative_path = md_file.relative_to(base_path)

                        docs.append(
                            {
                                "page_content": section.strip(),
                                "source_file": str(relative_path),
                                "metadata": {
                                    "file": str(relative_path),
                                    "category": relative_path.parts[0]
                                    if relative_path.parts
                                    else "general",
                                    "subcategory": relative_path.parts[1]
                                    if len(relative_path.parts) > 1
                                    else None,
                                },
                            }
                        )
            except Exception as e:
                print(f"Error loading {md_file}: {e}")
                continue

        return docs

    def _init_retriever(self) -> None:
        """Initialize the vector store retriever using global cache."""
        global _GLOBAL_RETRIEVER_CACHE, _GLOBAL_DOCS_LOADED

        if not _GLOBAL_DOCS_LOADED:
            docs = self._load_documentation()

            if docs:
                # Initialize embeddings model
                embeddings_model = OpenAIEmbeddings(model="text-embedding-3-small")

                # Create retriever and cache it globally
                _GLOBAL_RETRIEVER_CACHE = VectorStoreRetriever.from_docs(
                    docs, embeddings_model
                )
                _GLOBAL_DOCS_LOADED = True
            else:
                raise ValueError("No documentation files found in docs directory")

    def _run(
        self,
        query: str,
        k: int = 3,
        context: Optional[str] = None,
        config: Optional[RunnableConfig] = None,
    ) -> Tuple[str, DocumentationLookupArtifact]:
        """Search documentation for relevant information."""
        global _GLOBAL_RETRIEVER_CACHE

        try:
            # Initialize retriever if needed
            if not _GLOBAL_RETRIEVER_CACHE:
                self._init_retriever()

            # Auto-detect context from query if not provided
            if not context:
                context = self._detect_context_from_query(query)

            # Query the documentation using cached retriever
            results = _GLOBAL_RETRIEVER_CACHE.query(query, k=k, context_filter=context)

            # Format results
            doc_results = []
            for doc in results:
                doc_results.append(
                    DocumentationResult(
                        content=doc["page_content"],
                        source_file=doc["source_file"],
                        similarity=doc["similarity"],
                    )
                )

            # Create response text
            context_note = f" (filtered by context: {context})" if context else ""
            response_text = f"Found {len(results)} relevant documentation sections for '{query}'{context_note}:\n\n"
            for i, result in enumerate(doc_results, 1):
                response_text += f"{i}. From {result.source_file} (similarity: {result.similarity:.2f})\n"

            # Create artifact
            artifact = DocumentationLookupArtifact(results=doc_results, query=query)

            return response_text, artifact

        except Exception as e:
            error_msg = f"Error searching documentation: {str(e)}"
            return error_msg, DocumentationLookupArtifact(results=[], query=query)

    def _detect_context_from_query(self, query: str) -> Optional[str]:
        """Auto-detect context from query keywords."""
        query_lower = query.lower()

        # Define keyword patterns for context detection
        context_keywords = {
            "fields": [
                "field type",
                "field types",
                "number field",
                "text field",
                "date field",
                "file field",
                "boolean field",
                "rating field",
                "lookup field",
                "rollup field",
                "link to table",
                "collaborator field",
                "autonumber",
                "uuid field",
                "password field",
                "ai field",
                "primary field",
                "created by",
                "last modified",
                "single line text",
                "long text",
                "multiple select",
                "single select",
                "phone number",
                "email field",
                "url field",
                "duration field",
                "count field",
            ],
            "formulas": [
                "formula",
                "formulas",
                "formula field",
                "calculation",
                "function",
                "functions",
                "formula syntax",
                "formula reference",
                "concat",
                "upper",
                "lower",
                "if",
                "when",
                "sum",
                "avg",
                "count",
                "max",
                "min",
                "round",
                "abs",
                "now",
                "today",
                "date_diff",
                "date_add",
                "year",
                "month",
                "day",
                "formula function",
            ],
            "application-builder": [
                "element",
                "elements",
                "button element",
                "form element",
                "heading element",
                "text element",
                "image element",
                "table element",
                "input element",
                "checkbox element",
                "dropdown element",
                "iframe element",
                "login element",
                "repeat element",
                "rating element",
                "file input element",
                "columns element",
                "link element",
                "record selector",
                "date-time picker",
                "menu element",
                "multi-page container",
                "application builder",
                "app builder",
                "page builder",
                "element visibility",
                "element style",
                "element events",
            ],
            "views": [
                "view type",
                "view types",
                "grid view",
                "gallery view",
                "form view",
                "kanban view",
                "calendar view",
                "timeline view",
                "view configuration",
                "custom view",
                "collaborative view",
                "personal view",
                "export view",
                "form survey mode",
            ],
            "database": [
                "table",
                "tables",
                "create table",
                "database",
                "row",
                "rows",
                "data sync",
                "import data",
                "export table",
                "table configuration",
                "customize table",
            ],
            "security": [
                "permission",
                "permissions",
                "role",
                "roles",
                "rbac",
                "access control",
                "workspace permission",
                "database permission",
                "table permission",
                "field permission",
                "collaborator",
                "team",
                "member",
                "workspace member",
            ],
            "integrations": [
                "api",
                "webhook",
                "webhooks",
                "token",
                "database token",
                "zapier",
                "make",
                "n8n",
                "pipedream",
                "tooljet",
                "suretriggers",
                "integration",
                "third party",
            ],
            "dashboards": [
                "dashboard",
                "dashboards",
                "create dashboard",
                "dashboard configuration",
                "customize dashboard",
                "widgets",
                "chart",
                "charts",
            ],
        }

        # Check for keyword matches
        for context, keywords in context_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                return context

        return None

    async def _ainit_retriever(self) -> None:
        """Async initialize the vector store retriever with proper locking."""
        global _GLOBAL_INITIALIZATION_LOCK, _GLOBAL_DOCS_LOADED

        # Use lock to prevent multiple simultaneous initializations
        async with _GLOBAL_INITIALIZATION_LOCK:
            if not _GLOBAL_DOCS_LOADED:
                # Run the sync initialization in a thread pool
                await asyncio.to_thread(self._init_retriever)

    async def _aquery_retriever(
        self, query: str, k: int = 5, context_filter: Optional[str] = None
    ) -> List[Dict]:
        """Async query the cached retriever."""
        global _GLOBAL_RETRIEVER_CACHE

        # Run the sync query in a thread pool using cached retriever
        return await asyncio.to_thread(
            _GLOBAL_RETRIEVER_CACHE.query, query, k, context_filter
        )

    async def _arun(
        self,
        query: str,
        k: int = 3,
        context: Optional[str] = None,
        config: Optional[RunnableConfig] = None,
    ) -> Tuple[str, DocumentationLookupArtifact]:
        """Async version of documentation search."""
        return await sync_to_async(self._run)(query, k, context, config)

    @classmethod
    def clear_cache(cls):
        """Clear the cached retriever and documentation data."""
        global _GLOBAL_RETRIEVER_CACHE, _GLOBAL_DOCS_LOADED
        _GLOBAL_RETRIEVER_CACHE = None
        _GLOBAL_DOCS_LOADED = False


# Convenience function for direct use
def lookup_baserow_docs(query: str, k: int = 3) -> str:
    """
    Convenience function to search Baserow documentation.

    Args:
        query: The search query
        k: Number of results to return

    Returns:
        Concatenated documentation sections as a string
    """
    tool = DocumentationLookupTool()
    response, artifact = tool._run(query, k)

    # Return concatenated content
    return "\n\n---\n\n".join(
        [f"From {result.source_file}:\n{result.content}" for result in artifact.results]
    )
