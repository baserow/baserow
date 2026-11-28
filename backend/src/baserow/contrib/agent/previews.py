"""
Readable requests of the Agent's tools: values masked and lists cut to what
people can read, or shown whole to the person deciding on a held call.
"""

import re
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Any

from pydantic import BaseModel

from baserow.core.chat_runs.tool_input import held_tool_input, tool_input_preview

MAX_PREVIEW_ITEMS = 10
MAX_PREVIEW_KEYS = 10
MASKED_VALUE = "••••"

_held = ContextVar("agent_held_preview", default=False)


@contextmanager
def held_previews(held: bool = True) -> Iterator[None]:
    """
    Build the previews made inside for a call that waits for approval, or was
    approved: every requested item is named and every value shown whole, as the
    call sends it.

    :param held: Whether the call is held. A call that runs directly keeps the
        bounded preview.
    """

    token = _held.set(held)
    try:
        yield
    finally:
        _held.reset(token)


@dataclass
class StepPreview:
    """
    A call's request as people read it: what it works on, by name or else by ID,
    and the items it asks for under ``items_key``.
    """

    names: dict[str, Any]
    items_key: str | None = None
    items: list[Any] = dataclass_field(default_factory=list)
    truncated: bool = False
    """Whether items or keys were left out."""
    held: bool = dataclass_field(default_factory=_held.get)
    """Whether it's for a held call, whose values are all shown."""

    def cut_items(self, items: list[Any]) -> list[Any]:
        """
        :param items: The requested items, before their names are resolved.
        :return: The first ``MAX_PREVIEW_ITEMS`` of them, the only ones resolved,
            or all of them for a held call. The preview is marked as cut when
            items are left out.
        """

        if self.held:
            return items
        if len(items) > MAX_PREVIEW_ITEMS:
            self.truncated = True
        return items[:MAX_PREVIEW_ITEMS]

    def to_input(self) -> dict[str, Any]:
        """
        Bound the preview for the step's input: every list keeps its first
        ``MAX_PREVIEW_ITEMS`` items and every object its first ``MAX_PREVIEW_KEYS``
        keys, at any depth, and ``tool_input_preview`` shortens long strings. When
        the JSON is still too large to store, trailing items are left out until it
        fits, so the names always stay. When no item fits, the items are left out
        entirely rather than shown as an empty list.

        A held call's preview is stored whole instead, as ``held_tool_input``
        bounds it.

        :return: ``values``, and ``truncated`` when anything was left out.
        """

        if self.held:
            values = dict(self.names)
            if self.items_key is not None:
                values[self.items_key] = self.items
            return held_tool_input(values)
        items = cut(self.items)
        truncated = self.truncated or items != self.items
        while True:
            values: dict[str, Any] = dict(self.names)
            if self.items_key is not None and (items or not self.items):
                values[self.items_key] = items
            bounded = tool_input_preview(values)
            if bounded or not items:
                break
            items.pop()
            truncated = True
        if bounded and truncated:
            bounded["truncated"] = True
        return bounded


# The words of an argument name that may hold a credential, masked in what the
# owner approves. A name is split into words on anything but letters and digits
# and on camelCase, so ``passenger`` or ``max_tokens`` stay readable.
_NAME_WORD = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+")
_SECRET_WORDS = frozenset(
    {
        "pass",
        "passwd",
        "password",
        "passphrase",
        "secret",
        "secrets",
        "token",
        "apikey",
        "authorization",
        "authorisation",
        "credential",
        "credentials",
        "cookie",
        "cookies",
        "privatekey",
    }
)
_SECRET_WORD_PAIRS = frozenset({("api", "key"), ("private", "key")})
# Words that end a single-word name such as ``accesstoken`` or ``clientsecret``.
_SECRET_ENDINGS = (
    "password",
    "passphrase",
    "secret",
    "token",
    "apikey",
    "privatekey",
    "credential",
    "credentials",
)


# A name that starts with one of these counts or limits something, such as
# ``max_tokens``, so it holds no credential.
_COUNT_WORDS = frozenset({"max", "min", "num", "count", "total"})


def _singular(word: str) -> str:
    return word[:-1] if word.endswith("s") and not word.endswith("ss") else word


def is_secret_name(name: str) -> bool:
    """
    :param name: An argument's name.
    :return: Whether one of its words, singular or plural, or two that follow
        each other like ``api`` and ``key``, names a credential.
    """

    words = [_singular(word.lower()) for word in _NAME_WORD.findall(name)]
    if not words or words[0] in _COUNT_WORDS:
        return False
    return any(
        word in _SECRET_WORDS or word.endswith(_SECRET_ENDINGS) for word in words
    ) or not _SECRET_WORD_PAIRS.isdisjoint(zip(words, words[1:]))


def mask_secrets(value: Any) -> Any:
    """
    :param value: The arguments of a call to a tool Baserow doesn't know.
    :return: The value with every argument whose name may hold a credential
        masked, at any depth.
    """

    if isinstance(value, dict):
        return {
            key: MASKED_VALUE
            if isinstance(key, str) and is_secret_name(key)
            else mask_secrets(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [mask_secrets(item) for item in value]
    return value


def arguments_preview(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    :param arguments: The arguments of a call to a tool Baserow doesn't know.
    :return: The held call's request for the step's input: every argument whole,
        credentials masked, as ``held_tool_input`` bounds it.
    """

    return held_tool_input(mask_secrets(arguments))


def cut(value: Any) -> Any:
    """
    :param value: A requested value.
    :return: The value with every list cut to its first ``MAX_PREVIEW_ITEMS`` items
        and every object to its first ``MAX_PREVIEW_KEYS`` keys, at any depth.
    """

    if isinstance(value, list):
        return [cut(item) for item in value[:MAX_PREVIEW_ITEMS]]
    if isinstance(value, dict):
        return {key: cut(item) for key, item in list(value.items())[:MAX_PREVIEW_KEYS]}
    return value


def as_requested(value: Any) -> Any:
    """
    :param value: Validated tool arguments, or one of their values.
    :return: The value as JSON, with only what the model sent: defaults it left
        out stay out.
    """

    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_unset=True)
    if isinstance(value, dict):
        return {key: as_requested(item) for key, item in value.items()}
    if isinstance(value, list):
        return [as_requested(item) for item in value]
    return value


def mask(values: dict[str, Any], readable: set[str]) -> dict[str, Any]:
    """
    Show only values whose key is exactly a readable field's name, so a
    misspelled or unknown key can never reveal a password.

    :param values: One row's values by field name.
    :param readable: The names of the table's readable fields.
    :return: The values, with every other key's value masked.
    """

    return {
        name: value if name in readable else MASKED_VALUE
        for name, value in values.items()
    }


def name_field_references(value: Any, names: dict[int, str]) -> Any:
    """
    Name the fields a view or filter refers to: ``field_id`` becomes ``field`` and
    ``<x>_field_id`` becomes ``<x>_field``. An ID that isn't a field of the table
    stays as written, so the tool's own item error explains it.

    :param value: A view or filter request, or one of its values.
    :param names: The table's field names by ID.
    :return: The request with known field IDs replaced by names.
    """

    if isinstance(value, list):
        return [name_field_references(item, names) for item in value]
    if not isinstance(value, dict):
        return value
    named: dict[str, Any] = {}
    for key, item in value.items():
        if key.endswith("field_id") and isinstance(item, int) and item in names:
            named[key.removesuffix("_id")] = names[item]
        else:
            named[key] = name_field_references(item, names)
    return named
