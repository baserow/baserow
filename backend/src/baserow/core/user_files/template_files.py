import re
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator, Optional

TEMPLATE_FILE_PREFIX = "tpl"

TEMPLATE_WORKSPACE_ID_DIGITS = 10

# Uniques generated before template files existed can start with `tpl` by chance, so a
# template file is recognised by the prefix followed by the padded workspace id.
TEMPLATE_FILE_UNIQUE_PATTERN = (
    rf"^{TEMPLATE_FILE_PREFIX}[0-9]{{{TEMPLATE_WORKSPACE_ID_DIGITS}}}"
)
_template_file_unique_regex = re.compile(TEMPLATE_FILE_UNIQUE_PATTERN)

_template_file_owner: ContextVar[Optional[int]] = ContextVar(
    "template_file_owner", default=None
)


def template_file_prefix(workspace_id: int) -> str:
    """
    Returns the unique prefix of the files that belong to the template workspace.

    :param workspace_id: The id of the template workspace.
    :return: `tpl` followed by the zero-padded workspace id.
    """

    return f"{TEMPLATE_FILE_PREFIX}{workspace_id:0{TEMPLATE_WORKSPACE_ID_DIGITS}d}"


def is_template_file_unique(unique: str) -> bool:
    return bool(_template_file_unique_regex.match(unique))


def get_template_file_owner() -> Optional[int]:
    return _template_file_owner.get()


@contextmanager
def template_file_owner(workspace_id: int) -> Iterator[None]:
    """
    Makes every file uploaded inside the block a copy owned by the template workspace.

    :param workspace_id: The id of the template workspace that owns the files.
    """

    token = _template_file_owner.set(workspace_id)
    try:
        yield
    finally:
        _template_file_owner.reset(token)
