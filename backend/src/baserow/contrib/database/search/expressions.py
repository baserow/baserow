from django.contrib.postgres.search import SearchVector
from django.db.models import Expression


class LocalisedSearchVector(SearchVector):
    function = "try_set_tsv"

    """
    A `SearchVector` which is responsible for two additional requirements:

    1. The `SearchVector.config` is always set to what the value of
        `PG_FULLTEXT_SEARCH_CONFIG` is set to.
    2. The `Expression` given to it is always wrapped in `special_char_tokenizer`,
        a Django `Func` which converts specific characters in the text into spaces.
        See `special_char_tokenizer`'s docstring for more detailed information.

    Any new `FieldType` which should be searchable should have its
    `get_search_expression` return a `LocalisedSearchVector`, in only very
    specific cases would a `SearchVector` be used outside `FieldType`.
    """

    def __init__(self, expression: Expression, **kwargs) -> None:
        from baserow.contrib.database.search.handler import SearchHandler

        super().__init__(
            SearchHandler.special_char_tokenizer(expression),
            config=SearchHandler.search_config(),
            **kwargs,
        )
