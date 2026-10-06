from baserow.core.registry import Registry

from .mention_types import RowCommentMentionTargetType


class RowCommentMentionTargetTypeRegistry(Registry[RowCommentMentionTargetType]):
    """
    What `@` can address in a row comment. The user type lives in premium;
    other modules register their own (an agent that asked to be mentioned).
    """

    name = "row_comment_mention_target_type"


row_comment_mention_target_type_registry = RowCommentMentionTargetTypeRegistry()
