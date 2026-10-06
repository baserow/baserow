from prosemirror.model import Schema
from prosemirror.schema.basic import br_dom, p_dom

# Look at
# https://github.com/fellowapp/prosemirror-py/blob/main/prosemirror/schema/basic/schema_basic.py
# for the original source code of the basic schema.

nodes = {
    "doc": {"content": "block+"},
    "paragraph": {
        "content": "inline*",
        "group": "block",
        "parseDOM": [{"tag": "p"}],
        "toDOM": lambda _: p_dom,
        "toText": lambda node, fnc: "".join(
            fnc(child) for child in node.content.content
        ),
    },
    "text": {"group": "inline", "toText": lambda node, _: node.text},
    "hardBreak": {
        "inline": True,
        "group": "inline",
        "selectable": False,
        "parseDOM": [{"tag": "br"}],
        "toDOM": lambda _: br_dom,
        "toText": lambda node, _: "\n",
    },
    "mention": {
        "group": "inline",
        "inline": True,
        # `kind` tells a user mention from an application one (an agent that
        # asked to be mentioned); both share the same id space otherwise.
        "attrs": {
            "id": {"default": None},
            "label": {"default": None},
            "kind": {"default": "user"},
        },
        "toDOM": lambda node: [
            "span",
            {
                "class": "mention",
                "data-id": str(node.attrs["id"]),
                "data-label": node.attrs["label"],
                "data-kind": node.attrs["kind"],
                "data-type": "mention",
                "contenteditable": "false",
            },
            "@" + node.attrs["label"],
        ],
        "parseDOM": [
            {
                "tag": "span[data-id]",
                "getAttrs": lambda dom: {
                    "id": dom.getAttribute("data-id"),
                    "label": dom.getAttribute("data-label"),
                    "kind": dom.getAttribute("data-kind") or "user",
                },
            }
        ],
        "toText": lambda node, _: "@" + node.attrs["label"],
    },
}


schema = Schema({"nodes": nodes, "marks": {}})
