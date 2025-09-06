from pydantic import BaseModel, Field


class DocSearchToolArgsSchema(BaseModel):
    enhanced_question: str = Field(
        description=(
            "A reformulated English version of the user's question that incorporates relevant context and details."
        )
    )


class DocSearchArtifact(BaseModel):
    search_result: str = Field(description="The result of the search.")
    sources: list[str] = Field(
        description=(
            "A list of source documents used to generate the answer. "
            "If many sources are used, limit to the 3 most relevant ones."
        ),
        default_factory=list,
    )
