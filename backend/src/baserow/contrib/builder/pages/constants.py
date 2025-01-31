import re
import typing

from baserow.contrib.builder.pages.types import PAGE_PARAM_TYPE_CHOICES_LITERAL

# Every page param in a page path needs to be prefixed by the below symbol
PAGE_PATH_PARAM_PREFIX = ":"

PAGE_PARAM_TYPE_CHOICES = list(typing.get_args(PAGE_PARAM_TYPE_CHOICES_LITERAL))

# This regex needs to match the regex in `getPathParams` in the frontend
# (builder/utils/path.js)
PATH_PARAM_REGEX = re.compile("(:[A-Za-z0-9_]+)")
PATH_PARAM_EXACT_MATCH_REGEX = re.compile("(^:[A-Za-z0-9_]+)$")

QUERY_PARAM_EXACT_MATCH_REGEX = re.compile(r"(^[A-Za-z][A-Za-z0-9_-]*$)")

# This constant can be used to be inserted into a path temporarily as a unique
# placeholder since we already know the character can't be in the path (given it's
# illegal) we can establish uniqueness.
ILLEGAL_PATH_SAMPLE_CHARACTER = "^"
