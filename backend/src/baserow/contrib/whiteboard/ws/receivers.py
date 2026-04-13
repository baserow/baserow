# Whiteboard WS receivers.
# Currently, the whiteboard broadcasting is handled directly in the API views
# (WhiteboardView.put and BroadcastChangesView.post) rather than through
# Django signals, because there are no model-level signals for content updates.
