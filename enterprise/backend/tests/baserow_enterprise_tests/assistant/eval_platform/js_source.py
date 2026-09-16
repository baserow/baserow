"""Structural checks for the eval runner page's inline script.

The backend CI image ships no JavaScript engine, so the page's script is
checked here with a small tokenizer rather than ``node --check``. The checks
are deliberately structural: balance, function extraction and call arity. No
scope or type analysis is attempted.
"""

from __future__ import annotations

import re

_STRING_QUOTES = "\"'"
_REGEX_PRECEDING_CHARS = "(,=:[!&|?{};+-*/%<>~^"
_REGEX_PRECEDING_WORDS = frozenset(
    {"return", "typeof", "case", "in", "of", "new", "delete", "void", "instanceof"}
)
_AFTER_LITERAL = "\x00"

_SCRIPT_RE = re.compile(r"<script>(?P<body>.*?)</script>", re.DOTALL)
_FUNCTION_RE = re.compile(r"\b(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(")


def inline_script(page: str) -> str:
    """Return the body of the page's single inline ``<script>`` tag.

    :param page: The rendered HTML page.
    :raises AssertionError: If the page does not hold exactly one script tag.
    :return: The script body, without the surrounding tags.
    """

    scripts = _SCRIPT_RE.findall(page)
    assert len(scripts) == 1, (
        f"expected exactly one inline script, found {len(scripts)}"
    )
    return scripts[0]


def _blank_span(source: str) -> str:
    return "".join(character if character == "\n" else " " for character in source)


def _regex_can_start(previous: str, blanked_so_far: str) -> bool:
    if previous == _AFTER_LITERAL:
        return False
    if previous == "" or previous in _REGEX_PRECEDING_CHARS:
        return True
    word = re.search(r"([A-Za-z_$][\w$]*)\s*$", blanked_so_far)
    return bool(word) and word.group(1) in _REGEX_PRECEDING_WORDS


def _template_end(source: str, start: int) -> int:
    """Find the offset just past a template literal, spanning ``${}`` parts.

    :param source: JavaScript source.
    :param start: Offset of the opening backtick.
    :return: Offset just past the closing backtick.
    """

    index = start + 1
    length = len(source)
    depth = 0
    while index < length:
        character = source[index]
        if character == "\\":
            index += 2
            continue
        if character == "`" and depth == 0:
            return index + 1
        if character == "`":
            index = _template_end(source, index)
            continue
        if character == "$" and source[index : index + 2] == "${":
            depth += 1
            index += 2
            continue
        if character == "{" and depth:
            depth += 1
        elif character == "}" and depth:
            depth -= 1
        index += 1
    return length


def blank_literals(source: str) -> str:
    """Replace comments, strings, templates and regex literals with spaces.

    Offsets and line breaks are preserved so positions stay reportable.

    :param source: JavaScript source.
    :return: The source with every literal blanked out.
    """

    out: list[str] = []
    index = 0
    length = len(source)
    previous = ""
    while index < length:
        character = source[index]
        following = source[index + 1] if index + 1 < length else ""
        if character == "/" and following == "/":
            end = source.find("\n", index)
            end = length if end == -1 else end
        elif character == "/" and following == "*":
            end = source.find("*/", index + 2)
            end = length if end == -1 else end + 2
        elif character == "`":
            end = _template_end(source, index)
            previous = _AFTER_LITERAL
        elif character in _STRING_QUOTES:
            end = index + 1
            while end < length:
                if source[end] == "\\":
                    end += 2
                    continue
                if source[end] == character:
                    end += 1
                    break
                end += 1
            previous = _AFTER_LITERAL
        elif character == "/" and _regex_can_start(previous, "".join(out[-40:])):
            end = index + 1
            in_class = False
            while end < length:
                current = source[end]
                if current == "\\":
                    end += 2
                    continue
                if current == "\n":
                    break
                if current == "[":
                    in_class = True
                elif current == "]":
                    in_class = False
                elif current == "/" and not in_class:
                    end += 1
                    break
                end += 1
            previous = _AFTER_LITERAL
        else:
            out.append(character)
            if not character.isspace():
                previous = character
            index += 1
            continue
        out.append(_blank_span(source[index:end]))
        index = end
    return "".join(out)


def _line_of(source: str, offset: int) -> int:
    return source.count("\n", 0, offset) + 1


def _matching_brace(blanked: str, opening: int) -> int | None:
    depth = 0
    for offset in range(opening, len(blanked)):
        if blanked[offset] == "{":
            depth += 1
        elif blanked[offset] == "}":
            depth -= 1
            if depth == 0:
                return offset + 1
    return None


def declared_functions(source: str) -> list[str]:
    """List every named function declared in the script, in source order.

    :param source: JavaScript source.
    :return: The declared function names, with duplicates preserved.
    """

    return _FUNCTION_RE.findall(blank_literals(source))


def brace_problems(source: str) -> list[str]:
    """Report brace imbalance, and refuse to pass on a script it cannot read.

    :param source: JavaScript source.
    :return: One message per problem, empty when the source is well-formed.
    """

    blanked = blank_literals(source)
    problems: list[str] = []
    depth = 0
    for offset, character in enumerate(blanked):
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth < 0:
                problems.append(f"line {_line_of(source, offset)}: unmatched '}}'")
                depth = 0
    if depth != 0:
        problems.append(f"{depth} brace(s) never closed; the script cannot parse")
    if not _FUNCTION_RE.search(blanked):
        problems.append("no function declarations found; the checker cannot read this")
    return problems


def function_body(source: str, name: str) -> str:
    """Return the body of a named function, braces included.

    :param source: JavaScript source.
    :param name: The declared function name.
    :raises AssertionError: If the function is absent or never closed.
    :return: The function body from its opening brace to its closing brace.
    """

    blanked = blank_literals(source)
    match = re.search(rf"\b(?:async\s+)?function\s+{re.escape(name)}\s*\(", blanked)
    assert match, f"no function named {name}"
    opening = blanked.find("{", match.end())
    end = _matching_brace(blanked, opening) if opening != -1 else None
    assert end is not None, f"function {name} is never closed"
    return source[opening:end]


def call_arguments(source: str, name: str) -> list[list[str]]:
    """Split the top-level arguments of every call to a named function.

    :param source: JavaScript source.
    :param name: The called function name.
    :return: One list of argument expressions per call site.
    """

    blanked = blank_literals(source)
    calls: list[list[str]] = []
    for match in re.finditer(rf"(?<![\w$.]){re.escape(name)}\s*\(", blanked):
        preceding = blanked[: match.start()].rstrip()
        if preceding.endswith("function"):
            continue
        opening = match.end() - 1
        depth = 0
        arguments: list[str] = []
        start = opening + 1
        for offset in range(opening, len(blanked)):
            character = blanked[offset]
            if character in "([{":
                depth += 1
            elif character in ")]}":
                depth -= 1
                if depth == 0:
                    arguments.append(source[start:offset])
                    break
            elif character == "," and depth == 1:
                arguments.append(source[start:offset])
                start = offset + 1
        calls.append([argument.strip() for argument in arguments if argument.strip()])
    return calls
