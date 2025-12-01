from functools import partial

try:
    from functools import cached_property  # only present in python >= 3.8
except ImportError:
    from backports.cached_property import cached_property

import ast
from tokenize import COMMENT, TokenInfo, generate_tokens
from typing import Any, Dict, Generator, Iterable, List, Optional, Tuple, Type, Union

import pycodestyle

try:
    from flake8.engine import pep8 as stdin_utils
except ImportError:
    from flake8 import utils as stdin_utils


DocstringType = Union[ast.Constant, ast.Str]
ERR_MSG = "BDC001 - Baserow plugin: missing empty line after docstring"


class Token:
    def __init__(self, token: TokenInfo):
        self.token = token

    @property  # noqa: A003
    def type(self) -> int:
        return self.token[0]

    @property
    def start(self) -> Tuple[int, int]:
        return self.token[2]

    @property
    def start_row(self) -> int:
        return self.start[0]

    @property
    def col_offset(self) -> int:
        return self.start[1]


class FunctionNodeHelper:
    def __init__(self, node: ast.FunctionDef, comments: Dict[int, Token]):
        self.function_node = node
        self.comments = comments

    @cached_property
    def docstring(self) -> Optional[DocstringType]:
        if not self.function_node.body:
            return None

        first_node = self.function_node.body[0]
        if isinstance(first_node, ast.Expr) and isinstance(
            first_node.value, (ast.Constant, ast.Str)
        ):
            return first_node.value

        return None

    @cached_property
    def docstring_end_lineno(self) -> int:
        docstring = self.docstring
        return (
            docstring.end_lineno
            if hasattr(docstring, "end_lineno")
            else docstring.lineno
        )

    @cached_property
    def element_after_docstring(self) -> Optional[Union[Token, ast.AST]]:
        """
        Returns a node (comment or AST node) if it is in the line immediately after
        the docstring, otherwise returns None.
        """

        dostring_end_lineno = self.docstring_end_lineno
        comment = self.comments.get(dostring_end_lineno + 1, None)
        if comment is not None:
            return comment

        function_node = self.function_node
        second_node = function_node.body[1] if len(function_node.body) > 1 else None
        if second_node and second_node.lineno == dostring_end_lineno + 1:
            return second_node

        return None


def missing_empty_line_after_docstring(
    node: ast.FunctionDef,
    comments: Dict[int, Token],
) -> List[Tuple[int, int, str]]:
    """
    Check if there is at least one empty line after the docstring.

    NOTE: ast in python3.7 see docstrings as ast.Str and has no end_lineno attr,
          while in python3.10 it has end_lineno attr and is a ast.Constant.

    :param node: The function node to check.
    :return: A list of errors (if any) in the form [(line_no, column_no, error_msg)].
    """

    function_helper = FunctionNodeHelper(node, comments)
    if function_helper.docstring is None:
        return []

    elem = function_helper.element_after_docstring
    if elem is None:
        return []

    return [(function_helper.docstring_end_lineno, elem.col_offset, ERR_MSG)]


class Visitor(ast.NodeVisitor):
    def __init__(self, tokens) -> None:
        self.tokens = tokens
        self.errors: List[Tuple[int, int, str]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.errors += missing_empty_line_after_docstring(node, self.tokens)
        self.generic_visit(node)


class Plugin:
    name = "flake8_baserow_docstring"
    version = "0.1.0"

    _tokens = None

    def __init__(
        self,
        tree: ast.AST,
        filename: str = None,
        lines: Iterable[str] = None,
        file_tokens: Iterable[TokenInfo] = None,
    ):
        self._tree = tree
        self.filename = "stdin" if filename in ("stdin", "-", None) else filename
        if lines:
            if isinstance(lines, str):
                lines = lines.splitlines(True)
            self.lines = tuple(lines)
        self._tokens = file_tokens

    @cached_property
    def lines(self) -> Tuple[str, ...]:
        if self.filename == "stdin":
            return stdin_utils.stdin_get_value().splitlines(True)
        return pycodestyle.readlines(self.filename)

    @cached_property
    def tokens(self) -> Dict[int, Token]:
        if self._tokens is not None:
            tokens = self._tokens
        else:
            getter = partial(next, iter(self.lines))
            tokens = generate_tokens(getter)  # type: ignore
        comments = []
        for tkn in tokens:
            token = Token(tkn)
            if token.type == COMMENT:
                comments.append(token)
        return {comment.start_row: comment for comment in comments}

    def run(self) -> Generator[Tuple[int, int, str, Type[Any]], None, None]:
        visitor = Visitor(self.tokens)
        visitor.visit(self._tree)

        for line, col, msg in visitor.errors:
            yield line, col, msg, type(self)
