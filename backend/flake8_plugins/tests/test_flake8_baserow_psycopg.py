import ast
from flake8_baserow.psycopg import BaserowPsycopgChecker


def run_checker(code: str):
    tree = ast.parse(code)
    checker = BaserowPsycopgChecker(tree, "test.py")
    return list(checker.run())


def test_direct_import():
    code = """
import psycopg
import psycopg2
from psycopg import connect
from psycopg2 import connect as pg_connect
    """
    errors = run_checker(code)
    assert len(errors) == 4
    assert all(error[2].startswith("BPG001") for error in errors)


def test_allowed_import():
    code = """
from baserow.core.psycopg import connect
from baserow.core.psycopg import psycopg2
    """
    errors = run_checker(code)
    assert len(errors) == 0


def test_mixed_imports():
    code = """
import psycopg
from baserow.core.psycopg import connect
from psycopg2 import connect as pg_connect
    """
    errors = run_checker(code)
    assert len(errors) == 2
    assert errors[0][2].startswith("BPG001")
    assert errors[1][2].startswith("BPG001")
