from typing import Annotated
from pydantic import BaseModel, Field

from baserow_enterprise.assistant.types import BaseToolArgsSchema


class RetrieveKnowledgeToolArgsSchema(BaseToolArgsSchema):
    query: str = Field(
        description=(
            "A reformulated English version of the user's question that incorporates "
            "relevant context, Baserow specific terms and details."
        )
    )


class RetrieveKnowledgeToolArtifact(BaseModel):
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
