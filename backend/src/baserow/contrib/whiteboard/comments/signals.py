from django.dispatch import Signal

# Sent with: comment, whiteboard, user, mentions
whiteboard_comment_created = Signal()

# Sent with: comment, whiteboard, user, new_mentions (delta from prev set)
whiteboard_comment_updated = Signal()

# Sent with: comment_id, whiteboard, parent_comment_id, user
whiteboard_comment_deleted = Signal()

# Sent with: comment, whiteboard, user, resolved
whiteboard_comment_resolved = Signal()
