from pydantic import BaseModel, Field


class BaserowFormulaModel(BaseModel):
    formula: str = Field(description="The generated Baserow formula")
