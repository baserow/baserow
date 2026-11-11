from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict, create_model


class BaseModel(PydanticBaseModel):
    model_config = ConfigDict(
        extra="forbid",
        coerce_numbers_to_str=True,
    )


def without_field(
    model: type[PydanticBaseModel], name: str, field_name: str
) -> type[BaseModel]:
    """
    A model called ``name`` with the fields of ``model``, without ``field_name``, for
    a tool that takes that value as an argument of its own.
    """

    return create_model(
        name,
        __base__=BaseModel,
        __doc__=model.__doc__,
        __module__=model.__module__,
        **{
            key: (info.annotation, info)
            for key, info in model.model_fields.items()
            if key != field_name
        },
    )
