import ast
from flake8_baserow.ai_imports import BaserowAIImportsChecker


def run_checker(code: str):
    """Helper to run the checker on code and return errors."""
    tree = ast.parse(code)
    checker = BaserowAIImportsChecker(tree, "test.py")
    return list(checker.run())


def test_global_dspy_import():
    """Test that global dspy imports are flagged."""
    code = """
import dspy
"""
    errors = run_checker(code)
    assert len(errors) == 1
    assert "BAI001" in errors[0][2]
    assert "dspy" in errors[0][2]


def test_global_litellm_import():
    """Test that global litellm imports are flagged."""
    code = """
import litellm
"""
    errors = run_checker(code)
    assert len(errors) == 1
    assert "BAI001" in errors[0][2]
    assert "litellm" in errors[0][2]


def test_global_dspy_from_import():
    """Test that global 'from dspy import' statements are flagged."""
    code = """
from dspy import ChainOfThought
from dspy.predict import Predict
"""
    errors = run_checker(code)
    assert len(errors) == 2
    assert all("BAI001" in error[2] for error in errors)


def test_global_litellm_from_import():
    """Test that global 'from litellm import' statements are flagged."""
    code = """
from litellm import completion
from litellm.utils import get_llm_provider
"""
    errors = run_checker(code)
    assert len(errors) == 2
    assert all("BAI001" in error[2] for error in errors)


def test_local_import_in_function():
    """Test that local imports within functions are allowed."""
    code = """
def my_function():
    import dspy
    import litellm
    from dspy import ChainOfThought
    from litellm import completion
    return dspy, litellm
"""
    errors = run_checker(code)
    assert len(errors) == 0


def test_local_import_in_method():
    """Test that local imports within class methods are allowed."""
    code = """
class MyClass:
    def my_method(self):
        import dspy
        from litellm import completion
        return dspy.ChainOfThought()
"""
    errors = run_checker(code)
    assert len(errors) == 0


def test_local_import_in_async_function():
    """Test that local imports within async functions are allowed."""
    code = """
async def my_async_function():
    import dspy
    from litellm import acompletion
    return await acompletion()
"""
    errors = run_checker(code)
    assert len(errors) == 0


def test_mixed_global_and_local_imports():
    """Test that global imports are flagged while local imports are not."""
    code = """
import dspy  # This should be flagged

def my_function():
    import litellm  # This should be OK
    return litellm.completion()

from dspy import ChainOfThought  # This should be flagged
"""
    errors = run_checker(code)
    assert len(errors) == 2
    assert all("BAI001" in error[2] for error in errors)


def test_nested_function_imports():
    """Test that imports in nested functions are allowed."""
    code = """
def outer_function():
    def inner_function():
        import dspy
        from litellm import completion
        return dspy, completion
    return inner_function()
"""
    errors = run_checker(code)
    assert len(errors) == 0


def test_other_imports_not_affected():
    """Test that other imports are not flagged."""
    code = """
import os
import sys
from typing import List
from baserow.core.models import User
"""
    errors = run_checker(code)
    assert len(errors) == 0


def test_multiple_global_imports():
    """Test multiple global AI imports."""
    code = """
import dspy
import litellm
from dspy import ChainOfThought
from litellm import completion
import os  # This should not be flagged
"""
    errors = run_checker(code)
    assert len(errors) == 4
    assert all("BAI001" in error[2] for error in errors)


def test_import_with_alias():
    """Test that imports with aliases are also caught."""
    code = """
import dspy as d
import litellm as llm

def my_function():
    import dspy as local_d
    return local_d
"""
    errors = run_checker(code)
    assert len(errors) == 2
    assert all("BAI001" in error[2] for error in errors)


def test_submodule_imports():
    """Test that submodule imports are caught at global scope."""
    code = """
from dspy.teleprompt import BootstrapFewShot
from litellm.utils import token_counter

def my_function():
    from dspy.predict import Predict
    from litellm.integrations import log_event
    return Predict, log_event
"""
    errors = run_checker(code)
    assert len(errors) == 2
    assert all("BAI001" in error[2] for error in errors)
    # Verify the errors are for the global imports
    assert errors[0][0] == 2  # Line number of first import
    assert errors[1][0] == 3  # Line number of second import


def test_class_method_and_staticmethod():
    """Test that imports in classmethods and staticmethods are allowed."""
    code = """
class MyClass:
    @classmethod
    def my_classmethod(cls):
        import dspy
        return dspy

    @staticmethod
    def my_staticmethod():
        from litellm import completion
        return completion
"""
    errors = run_checker(code)
    assert len(errors) == 0


def test_lambda_not_considered_function():
    """Test that imports in lambdas (which aren't supported anyway) at module level are flagged."""
    code = """
# Note: This is contrived since you can't actually have imports in lambdas,
# but this tests that lambda doesn't count as a function scope
import dspy
"""
    errors = run_checker(code)
    assert len(errors) == 1
    assert "BAI001" in errors[0][2]
