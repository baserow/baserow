"""
Changes the filters of Local Baserow services: the data sources of applications and
dashboards, and automation nodes reading rows from a table.

Each object owning such a service registers a ``ServiceFilterTargetType`` saying how
to find it, check it may be changed, check its formula values and save new filters
through its own undoable action, so every client changes them the way the editor
does.
"""
