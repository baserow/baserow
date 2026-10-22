from unittest.mock import MagicMock
from uuid import uuid4

from django.apps import apps
from django.urls import reverse

import pytest
from freezegun import freeze_time
from health_check.exceptions import ServiceWarning
from health_check.plugins import plugin_dir

from baserow.config import streaming
from baserow.core import tasks
from baserow.core.chat_runs.constants import PRUNE_INTERVAL, SWEEP_INTERVAL
from baserow.core.chat_runs.health_checks import ChatRunsHealthCheck
from baserow.core.chat_runs.models import ChatRun
from baserow.core.chat_runs.pages import ChatRunsPageType
from baserow.core.chat_runs.tasks import (
    execute_chat_run,
    prune_chat_runs,
    sweep_chat_runs,
)
from baserow.ws.registries import page_registry


def test_engine_model_tasks_health_and_discovery_belong_to_core():
    assert apps.get_model("core", "ChatRun") is ChatRun
    assert ChatRun._meta.app_label == "core"
    assert tasks.execute_chat_run is execute_chat_run
    assert execute_chat_run.acks_late is False
    assert execute_chat_run.max_retries == 0
    assert execute_chat_run.ignore_result
    assert isinstance(page_registry.get("chat_runs"), ChatRunsPageType)
    assert ChatRunsHealthCheck in [entry[0] for entry in plugin_dir._registry]
    stream = reverse("api:chat_runs:stream", kwargs={"run_id": uuid4()})
    assert any(
        methods == ("GET",) and pattern.fullmatch(stream)
        for pattern, methods in streaming._paths
    )
    sender = MagicMock()
    tasks.setup_periodic_chat_run_tasks(sender)
    scheduled = [
        (call.args[0], call.args[1].task)
        for call in sender.add_periodic_task.call_args_list
    ]
    assert scheduled == [
        (SWEEP_INTERVAL, sweep_chat_runs.name),
        (PRUNE_INTERVAL, prune_chat_runs.name),
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "claim,ok,warn", [(False, "10:04", "10:06"), (True, "10:02", "10:04")]
)
def test_health_warns_when_workers_or_sweeper_are_missing(create_run, claim, ok, warn):
    with freeze_time("2026-10-16 10:00"):
        create_run(claim=claim)
    with freeze_time(f"2026-10-16 {ok}"):
        ChatRunsHealthCheck().check_status()
    with freeze_time(f"2026-10-16 {warn}"), pytest.raises(ServiceWarning):
        ChatRunsHealthCheck().check_status()
