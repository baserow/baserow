import copy
from typing import Dict, NamedTuple

from django.conf import settings
from django.core import mail
from django.core.mail import EmailMessage

from health_check.contrib.s3boto3_storage.backends import S3Boto3StorageHealthCheck
from health_check.plugins import plugin_dir
from health_check.storage.backends import DefaultFileStorageHealthCheck


class HealthCheckResult(NamedTuple):
    checks: Dict[str, str]
    passing: bool


class HealthCheckHandler:
    @classmethod
    def get_plugins(cls):
        return sorted(
            (
                plugin_class(**copy.deepcopy(options))
                for plugin_class, options in plugin_dir._registry
            ),
            key=lambda plugin: plugin.identifier(),
        )

    @classmethod
    def run_all_checks(cls) -> HealthCheckResult:
        """
        The health_check library provides its own template and view. However, it has
        bugs, runs health checks in threads which causes further problems and does
        not fit into our DRF based authentication. We just use this library
        for the nice suite of health check plugins it provides, and use its python
        API to run those in a simpler and safer fashion in this method.
        """

        checks = {}

        passing = True
        for plugin in cls.get_plugins():
            if cls._should_skip_check(plugin):
                continue
            # The plugin checks can fail and raise but we always want to catch
            # to report back that they failed.
            # noinspection PyBroadException
            try:
                plugin.run_check()
            except Exception:  # nosec
                pass
            checks[str(plugin.identifier())] = str(plugin.pretty_status())
            if plugin.critical_service and not plugin.status:
                passing = False

        return HealthCheckResult(checks, passing)

    @classmethod
    def _should_skip_check(cls, plugin):
        """
        Make sure we skip the s3 check when s3 is not active and vice versa with
        the default storage check.
        """

        s3_enabled = (
            settings.STORAGES["default"]["BACKEND"]
            == "storages.backends.s3boto3.S3Boto3Storage"
        )
        if s3_enabled:
            return isinstance(plugin, DefaultFileStorageHealthCheck)
        else:
            return isinstance(plugin, S3Boto3StorageHealthCheck)

    @classmethod
    def send_test_email(cls, target_email: str):
        """
        This method sends a test email synchronously and will raise any exceptions
        that occur.

        To do this it forces the backend not to be the celery one, which triggers a
        celery task when `email.send` is called, but instead the normal backend that
        celery itself would have been using within that task.

        Sending via a celery task makes this test pointless as we can't get the result
        back from the celery task. So this way we force the email to be sent
        synchronously, so we can immediately see any errors and respond with
        them back to the user.

        :param target_email: The email address to send the test email to.
        :raises: Will attempt to send the email and will raise any Exceptions that occur
            if the sending fails.
        """

        with mail.get_connection(
            fail_silently=False, backend=settings.CELERY_EMAIL_BACKEND
        ) as connection:
            email = EmailMessage(
                "Test email from TCR Projects",
                "This is a test email sent by the email tester in TCR Projects",
                settings.FROM_EMAIL,
                [target_email],
                connection=connection,
            )
            email.send(fail_silently=False)
