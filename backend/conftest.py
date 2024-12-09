# # conftest.py
#
# import pytest
# from django.conf import settings
# from django.core.management import call_command
# from django.test.utils import setup_databases, teardown_databases
#
#
# @pytest.fixture(autouse=True)
# def db_flush(django_db_blocker):
#     """Fixture to flush the test database before each test session"""
#     with django_db_blocker.unblock():
#         call_command("flush", verbosity=0, interactive=False)
